'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { baseUrl } from '@/lib/api';
import { Check, Copy, Server } from 'lucide-react';
import { useState } from 'react';

const mcpUrl = `${baseUrl}/mcp/`;

const claudeCodeCommand = `claude mcp add-json "draft-detective" '{"type":"http","url":"${mcpUrl}"}'`;

const codexCommand = `codex mcp add draft-detective --url ${mcpUrl}`;

const sampleTriggers = [
  'Use Draft Detective to extract claims from this paper: <paste-markdown-or-path>',
  'Run a reference validation review on this manuscript with Draft Detective.',
  'Check figures and tables in this document using Draft Detective and summarize the findings.',
  'List the available Draft Detective workflows and recommend which ones to run on this draft.',
];

function CopyableCode({ code, multiline = false }: { code: string; multiline?: boolean }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex items-start gap-2">
      <code
        className={`flex-1 rounded-md bg-muted px-3 py-2 text-sm font-mono break-all ${
          multiline ? 'whitespace-pre overflow-x-auto' : ''
        }`}
      >
        {code}
      </code>
      <Button variant="outline" onClick={handleCopy} title="Copy">
        {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
        {copied ? 'Copied' : 'Copy'}
      </Button>
    </div>
  );
}

export function McpInstructions() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Server className="h-6 w-6" />
          MCP Server
        </h1>
        <p className="text-muted-foreground mt-1">
          Connect Draft Detective to Claude or any MCP-compatible client to run reviews directly from your AI assistant.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Your MCP Server URL</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <CopyableCode code={mcpUrl} />
          <p className="text-sm text-muted-foreground">
            Paste this URL when adding the integration in your MCP client.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Install instructions</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="claude-code">
            <TabsList>
              <TabsTrigger value="claude-code">Claude Code</TabsTrigger>
              <TabsTrigger value="codex">Codex</TabsTrigger>
              <TabsTrigger value="opencode">Opencode</TabsTrigger>
            </TabsList>
            <TabsContent value="claude-code" className="space-y-3 mt-4">
              <p className="text-sm text-muted-foreground">
                Run this command in your terminal to register the MCP server with Claude Code:
              </p>
              <CopyableCode code={claudeCodeCommand} />
              <p className="text-sm text-muted-foreground">
                After adding it, run <code className="font-mono text-xs">/mcp</code> inside Claude Code to authenticate.
              </p>
            </TabsContent>
            <TabsContent value="codex" className="space-y-3 mt-4">
              <p className="text-sm text-muted-foreground">
                Run this command in your terminal to register the MCP server with Codex:
              </p>
              <CopyableCode code={codexCommand} />
              <p className="text-sm text-muted-foreground">
                A browser window will open the first time you use it so you can authenticate.
              </p>
            </TabsContent>
            <TabsContent value="opencode" className="space-y-3 mt-4">
              <p className="text-sm text-muted-foreground">In your terminal, run the interactive add command:</p>
              <CopyableCode code="opencode mcp add" />
              <p className="text-sm text-muted-foreground">Answer the prompts as follows:</p>
              <ul className="text-sm text-muted-foreground list-disc pl-5 space-y-1">
                <li>
                  <strong>Location:</strong> <code className="font-mono text-xs">Global</code> (or{' '}
                  <code className="font-mono text-xs">Project</code> if you only want it in this project)
                </li>
                <li>
                  <strong>MCP server name:</strong> <code className="font-mono text-xs">Draft Detective</code>
                </li>
                <li>
                  <strong>MCP server type:</strong> <code className="font-mono text-xs">Remote</code>
                </li>
                <li>
                  <strong>MCP server URL:</strong> <code className="font-mono text-xs break-all">{mcpUrl}</code>
                </li>
                <li>
                  <strong>Does this server require OAuth authentication?</strong>{' '}
                  <code className="font-mono text-xs">Yes</code>
                </li>
                <li>
                  <strong>Do you have a pre-registered client ID?</strong> <code className="font-mono text-xs">No</code>
                </li>
              </ul>
              <p className="text-sm text-muted-foreground">Then authenticate:</p>
              <CopyableCode code="opencode mcp auth" />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">How to use</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Once installed, just ask your AI assistant in plain English. Here are some prompts to get you started:
          </p>
          <ul className="space-y-3">
            {sampleTriggers.map((trigger) => (
              <li key={trigger} className="rounded-md bg-muted px-3 py-2 text-sm font-mono break-words">
                {trigger}
              </li>
            ))}
          </ul>
          <p className="text-sm text-muted-foreground">
            The assistant will pick the right Draft Detective tools (creating a project, running a workflow, fetching
            results) and walk you through the analysis.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
