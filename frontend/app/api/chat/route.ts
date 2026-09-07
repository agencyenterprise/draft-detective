import { openai } from '@ai-sdk/openai';
import { jsonSchema, stepCountIs, streamText, tool, type ModelMessage } from 'ai';
import { auth } from '@/auth';
import { DEFAULT_MODEL_ID, getChatModel } from '@/lib/chat-models';
import { SKILLS } from '@/lib/generated-skills';

// Skill-following can take several model steps, so allow a longer budget.
export const maxDuration = 60;

const SKILL_NAMES = SKILLS.map((skill) => skill.name);
const SKILL_BY_NAME = new Map(SKILLS.map((skill) => [skill.name, skill]));
const SKILL_CATALOG = SKILLS.map((skill) => `- ${skill.name}: ${skill.description}`).join('\n');

const SYSTEM_PROMPT = `You are Draft Detective, an AI assistant specialized in peer review of academic papers and policy research.

Your purpose is to help researchers, analysts, and reviewers assess and improve manuscripts and policy reports before formal peer review. You focus on the substance of the work: the soundness of claims and citations, the validity of reasoning and methodology, the accuracy of references, the completeness and consistency of structure, figures, and tables, and the clarity and neutrality of the writing.

How you work:
- Be rigorous, precise, and candid, but constructive — a clearly identified weakness is a gift to the author.
- Ground every judgment in the text the user provides. Do not invent findings, sources, or quotations. If you need the document (or a specific section) and it has not been provided, ask for it.
- When you make claims about a document, cite the specific passages you are relying on.
- You can search the web with the \`web_search\` tool. Use it to find current information and to locate and verify sources, references, and related literature — and cite the URLs you rely on. Do not rely on memory for factual claims about real-world sources.
- Web search sends the user's text to an external provider, so a check that searches on their document needs their explicit consent first. The skills that do this (\`reference-validation\`, \`reference-download\`, \`methodology-comparison\`) open with the consent step and the wording to relay — follow it, and wait for an explicit yes before the first search. One consent covers that document for the rest of the conversation. Searching for general background that carries no document content does not need it.
- Keep general conversation helpful and on-topic for peer review and research quality.

You have access to a set of specialized Draft Detective skills. Each skill contains detailed expert instructions for a specific review task. When a user's request matches a skill, call the \`load_skill\` tool with its exact name to load the full instructions, then follow them precisely. You may load more than one skill when a task calls for it (some skills reference others). Do not fabricate a skill's contents — always load it.

One of them, \`voice-and-tone\`, governs how you write rather than what to check. Load it before drafting anything substantial that a person will read — findings, a review, a memo, a summary, recommendations, an answer explaining what is wrong with a draft — and follow it for the wording. A short factual reply or a clarifying question does not need it. Where a task skill specifies content, structure, or formatting, that skill wins; \`voice-and-tone\` governs the wording.

Available skills:
${SKILL_CATALOG}`;

const loadSkill = tool({
  description:
    'Load the full expert instructions for one of the available Draft Detective skills, by its exact name. Call this before performing a review task that matches a skill, then follow the returned instructions.',
  inputSchema: jsonSchema<{ name: string }>({
    type: 'object',
    properties: {
      name: { type: 'string', enum: SKILL_NAMES, description: 'The exact skill name to load.' },
    },
    required: ['name'],
    additionalProperties: false,
  }),
  execute: async ({ name }) => {
    const skill = SKILL_BY_NAME.get(name);
    if (!skill) {
      return `Unknown skill "${name}". Available skills: ${SKILL_NAMES.join(', ')}.`;
    }
    return skill.instructions;
  },
});

interface ChatRequestBody {
  messages: ModelMessage[];
  // The model id selected in the assistant-ui Model Selector (arrives via the
  // registered ModelContext as `config.modelName`).
  model?: string;
}

export async function POST(req: Request): Promise<Response> {
  const session = await auth();
  if (!session?.user) {
    return new Response('Unauthorized', { status: 401 });
  }

  const { messages, model }: ChatRequestBody = await req.json();

  // Resolve the model against the allowlist. Falls back to the default when the
  // client omits or sends an unknown model, so the route can never be driven to
  // an arbitrary model.
  const chatModel = (model ? getChatModel(model) : undefined) ?? getChatModel(DEFAULT_MODEL_ID)!;

  if (!process.env.OPENAI_API_KEY) {
    return Response.json({ error: 'OPENAI_API_KEY is not configured on the server.' }, { status: 500 });
  }

  const result = streamText({
    model: openai(chatModel.id),
    // Fixed Draft Detective persona + skill catalog; not overridable by the client.
    system: SYSTEM_PROMPT,
    messages,
    tools: {
      load_skill: loadSkill,
      // OpenAI-hosted web search (Responses API). Available by default; the
      // model calls it when a task needs current info or source verification.
      web_search: openai.tools.webSearch(),
    },
    // Let the model call tools and then continue with its answer in the same request.
    stopWhen: stepCountIs(10),
    // Every offered model is reasoning-capable; ask for summarized reasoning so
    // the chain-of-thought UI can display it.
    providerOptions: { openai: { reasoningSummary: 'auto' } },
  });

  // Stream the full event stream (reasoning, tool calls, tool results, text) as
  // newline-delimited JSON so the client can render the chain of thought. Tools
  // still execute server-side; here we also surface each step to the UI.
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const write = (event: Record<string, unknown>) =>
        controller.enqueue(encoder.encode(`${JSON.stringify(event)}\n`));
      try {
        for await (const part of result.fullStream) {
          switch (part.type) {
            case 'text-delta':
              write({ t: 'text', v: part.text });
              break;
            case 'reasoning-delta':
              write({ t: 'reasoning', v: part.text });
              break;
            case 'tool-call':
              write({ t: 'tool', id: part.toolCallId, name: part.toolName, args: part.input });
              break;
            case 'tool-result':
              write({ t: 'tool_result', id: part.toolCallId, result: part.output });
              break;
            case 'tool-error':
              write({
                t: 'tool_result',
                id: part.toolCallId,
                result: { error: part.error instanceof Error ? part.error.message : String(part.error) },
                isError: true,
              });
              break;
            case 'error':
              write({ t: 'error', v: part.error instanceof Error ? part.error.message : String(part.error) });
              break;
          }
        }
      } catch (error) {
        write({ t: 'error', v: error instanceof Error ? error.message : 'Stream failed.' });
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: { 'Content-Type': 'application/x-ndjson; charset=utf-8', 'Cache-Control': 'no-cache' },
  });
}
