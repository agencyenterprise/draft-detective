import { Issue } from '@/lib/generated-api';

const MARKER_TAG = 'AIReviewer_Issue_Marker';
const AUTH_TOKEN_PROPERTY = 'AIReviewer_AuthToken';
const PARAGRAPH_LINE_RANGES_PROPERTY = 'AIReviewer_ParagraphLineRanges';

type ParagraphLineRanges = Record<string, [number, number]>;

function findParagraphByLineRange(
  paragraphLineRanges: ParagraphLineRanges,
  startLine: number,
  endLine: number,
): number | null {
  let best: number | null = null;
  for (const [paraKey, range] of Object.entries(paragraphLineRanges)) {
    const [paraStart, paraEnd] = range;
    if (paraStart <= endLine && paraEnd >= startLine) {
      const paraIndex = Number(paraKey);
      if (best === null || paraIndex < best) {
        best = paraIndex;
      }
    }
  }
  return best;
}

function resolveIssueParagraphIndex(issue: Issue, paragraphLineRanges: ParagraphLineRanges): number | null {
  if (typeof issue.start_line !== 'number' || typeof issue.end_line !== 'number') {
    return null;
  }
  return findParagraphByLineRange(paragraphLineRanges, issue.start_line, issue.end_line);
}

function buildIssuesMap(issues: Issue[], paragraphLineRanges: ParagraphLineRanges): Map<number, Issue[]> {
  const map = new Map<number, Issue[]>();
  issues.forEach((issue) => {
    const paragraphIndex = resolveIssueParagraphIndex(issue, paragraphLineRanges);
    if (paragraphIndex === null) return;
    if (!map.has(paragraphIndex)) {
      map.set(paragraphIndex, []);
    }
    const list = map.get(paragraphIndex)!;
    if (!list.includes(issue)) {
      list.push(issue);
    }
  });
  return map;
}

export async function loadSettings(): Promise<{
  authToken: string | null;
  paragraphLineRanges: ParagraphLineRanges | null;
}> {
  return new Promise((resolve, reject) => {
    try {
      if (typeof Office === 'undefined' || !Office.context || !Office.context.document) {
        resolve({
          authToken: null,
          paragraphLineRanges: null,
        });
        return;
      }

      Office.context.document.settings.refreshAsync(async (result) => {
        if (result.status === Office.AsyncResultStatus.Succeeded) {
          const customProps = await getCustomDocumentProperties();
          resolve({
            authToken: customProps.authToken,
            paragraphLineRanges: customProps.paragraphLineRanges,
          });
        } else {
          console.error('Failed to refresh settings: ' + result.error.message);
          reject(result.error);
        }
      });
    } catch (error) {
      console.error('Error loading settings: ' + error);
      reject(error);
    }
  });
}

export async function getCustomDocumentProperties(): Promise<{
  authToken: string | null;
  paragraphLineRanges: ParagraphLineRanges | null;
}> {
  if (typeof Word === 'undefined') {
    return { authToken: null, paragraphLineRanges: null };
  }

  try {
    return await Word.run(async (context) => {
      const props = context.document.properties.customProperties;
      const tokenProp = props.getItemOrNullObject(AUTH_TOKEN_PROPERTY);
      const paragraphLineRangesProp = props.getItemOrNullObject(PARAGRAPH_LINE_RANGES_PROPERTY);
      tokenProp.load(['name', 'value']);
      paragraphLineRangesProp.load(['name', 'value']);
      await context.sync();

      const paragraphLineRanges = paragraphLineRangesProp.isNullObject
        ? null
        : (JSON.parse(String(paragraphLineRangesProp.value ?? '{}')) as ParagraphLineRanges);

      return {
        authToken: tokenProp.isNullObject ? null : String(tokenProp.value ?? ''),
        paragraphLineRanges,
      };
    });
  } catch (error) {
    console.error('Error reading custom document properties:', error);
    return { authToken: null, paragraphLineRanges: null };
  }
}

export async function getCurrentParagraphIndex(): Promise<number> {
  if (typeof Word === 'undefined') return -1;

  return await Word.run(async (context) => {
    try {
      const selection = context.document.getSelection();
      const contentControl = selection.parentContentControlOrNullObject;
      contentControl.load('tag');
      await context.sync();
      if (!contentControl.isNullObject && contentControl.tag.startsWith(MARKER_TAG)) {
        const tag = String(contentControl.tag ?? '');
        const match = tag.match(/\d+/);
        if (match) {
          return Number(match[0]);
        }
      }

      return -1;
    } catch (error) {
      console.warn('Could not determine paragraph index (possibly in header/footer or outside body):', error);
      return -1;
    }
  });
}

async function selectParagraph(paragraphIndex: number): Promise<void> {
  await Word.run(async (context) => {
    const tag = `${MARKER_TAG}:${paragraphIndex}`;
    const contentControls = context.document.contentControls.getByTag(tag).getFirstOrNullObject();
    await context.sync();
    if (!contentControls.isNullObject) {
      contentControls.select();
      await context.sync();
    }
  });
}

export async function jumpToIssue(issue: Issue): Promise<void> {
  if (typeof Word === 'undefined') return;

  const { paragraphLineRanges } = await getCustomDocumentProperties();
  if (!paragraphLineRanges) {
    console.warn('No paragraph line-range mapping found');
    return;
  }

  const paragraphIndex = resolveIssueParagraphIndex(issue, paragraphLineRanges);
  if (paragraphIndex === null) {
    console.warn('No paragraph found for issue', issue.id);
    return;
  }

  await selectParagraph(paragraphIndex);
}

export async function addIssueMarkers(issues: Issue[]): Promise<Map<number, Issue[]>> {
  if (typeof Word === 'undefined') return new Map();
  const { paragraphLineRanges } = await getCustomDocumentProperties();
  if (!paragraphLineRanges) return new Map();
  return buildIssuesMap(issues, paragraphLineRanges);
}
