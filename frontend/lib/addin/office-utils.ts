import { DocumentIssue } from '@/lib/generated-api';

function buildIssuesMap(
  issues: DocumentIssue[],
  chunkToParagraphMapping: Record<string, number>,
): Map<number, DocumentIssue[]> {
  const map = new Map<number, DocumentIssue[]>();
  issues.forEach((issue) => {
    const indicesToProcess = new Set<number>();
    if (issue.chunk_index !== undefined && issue.chunk_index !== null) {
      indicesToProcess.add(issue.chunk_index);
    }
    if (issue.chunk_indices) {
      issue.chunk_indices.forEach((idx) => indicesToProcess.add(idx));
    }
    indicesToProcess.forEach((chunkIndex) => {
      const paragraphIndex = chunkToParagraphMapping[String(chunkIndex)];
      if (paragraphIndex !== undefined) {
        if (!map.has(paragraphIndex)) {
          map.set(paragraphIndex, []);
        }
        const list = map.get(paragraphIndex)!;
        if (!list.includes(issue)) {
          list.push(issue);
        }
      }
    });
  });
  return map;
}

export async function loadSettings(): Promise<{
  authToken: string | null;
  chunkToParagraphMapping: Record<string, number> | null;
}> {
  return new Promise((resolve, reject) => {
    try {
      if (typeof Office === 'undefined' || !Office.context || !Office.context.document) {
        resolve({
          authToken: null,
          chunkToParagraphMapping: null,
        });
        return;
      }

      Office.context.document.settings.refreshAsync(async (result) => {
        if (result.status === Office.AsyncResultStatus.Succeeded) {
          const customProps = await getCustomDocumentProperties();
          resolve({
            authToken: customProps.authToken,
            chunkToParagraphMapping: customProps.chunkToParagraphMapping,
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
  chunkToParagraphMapping: Record<string, number> | null;
}> {
  if (typeof Word === 'undefined') {
    return { authToken: null, chunkToParagraphMapping: null };
  }

  try {
    return await Word.run(async (context) => {
      const props = context.document.properties.customProperties;
      const tokenProp = props.getItemOrNullObject('AIReviewer_AuthToken');
      const chunkToParagraphMappingProp = props.getItemOrNullObject('AIReviewer_ChunkToParagraphMapping');
      tokenProp.load(['name', 'value']);
      chunkToParagraphMappingProp.load(['name', 'value']);
      await context.sync();

      const chunkToParagraphMapping = chunkToParagraphMappingProp.isNullObject
        ? null
        : JSON.parse(String(chunkToParagraphMappingProp.value ?? '{}'));

      return {
        authToken: tokenProp.isNullObject ? null : String(tokenProp.value ?? ''),
        chunkToParagraphMapping,
      };
    });
  } catch (error) {
    console.error('Error reading custom document properties:', error);
    return { authToken: null, chunkToParagraphMapping: null };
  }
}

export async function getCurrentParagraphIndex(): Promise<number> {
  if (typeof Word === 'undefined') return -1;

  return Word.run(async (context) => {
    try {
      const selection = context.document.getSelection();
      const contentControl = selection.contentControls.getFirstOrNullObject();
      contentControl.load(['tag', 'title']);
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

const MARKER_TAG = 'AIReviewer_Issue_Marker';

export async function addIssueMarkers(issues: DocumentIssue[]): Promise<Map<number, DocumentIssue[]>> {
  if (typeof Word === 'undefined') return new Map();

  const issuesMap = await Word.run(async (context) => {
    const { chunkToParagraphMapping } = await getCustomDocumentProperties();
    if (!chunkToParagraphMapping) return new Map();
    return buildIssuesMap(issues, chunkToParagraphMapping);
  });

  return issuesMap;
}
