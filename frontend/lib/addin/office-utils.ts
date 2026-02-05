import { DocumentIssue, SeverityEnum } from '@/lib/generated-api';

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
  projectId: string | null;
  authToken: string | null;
  issueMarkersApplied: boolean;
  chunkToParagraphMapping: Record<string, number> | null;
}> {
  return new Promise((resolve, reject) => {
    try {
      if (typeof Office === 'undefined' || !Office.context || !Office.context.document) {
        resolve({
          projectId: null,
          authToken: null,
          issueMarkersApplied: false,
          chunkToParagraphMapping: null,
        });
        return;
      }

      Office.context.document.settings.refreshAsync(async (result) => {
        if (result.status === Office.AsyncResultStatus.Succeeded) {
          const customProps = await getCustomDocumentProperties();
          resolve({
            projectId: customProps.projectId,
            authToken: customProps.authToken,
            issueMarkersApplied: customProps.issueMarkersApplied,
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
  projectId: string | null;
  authToken: string | null;
  issueMarkersApplied: boolean;
  chunkToParagraphMapping: Record<string, number> | null;
}> {
  if (typeof Word === 'undefined') {
    return { projectId: null, authToken: null, issueMarkersApplied: false, chunkToParagraphMapping: null };
  }

  try {
    return await Word.run(async (context) => {
      const props = context.document.properties.customProperties;
      const projectProp = props.getItemOrNullObject('AIReviewer_ProjectId');
      const tokenProp = props.getItemOrNullObject('AIReviewer_AuthToken');
      const markersProp = props.getItemOrNullObject('AIReviewer_IssueMarkersApplied');
      const chunkToParagraphMappingProp = props.getItemOrNullObject('AIReviewer_ChunkToParagraphMapping');
      projectProp.load(['name', 'value']);
      tokenProp.load(['name', 'value']);
      markersProp.load(['name', 'value']);
      chunkToParagraphMappingProp.load(['name', 'value']);
      await context.sync();

      const chunkToParagraphMapping = chunkToParagraphMappingProp.isNullObject
        ? null
        : JSON.parse(String(chunkToParagraphMappingProp.value ?? '{}'));

      return {
        projectId: projectProp.isNullObject ? null : String(projectProp.value ?? ''),
        authToken: tokenProp.isNullObject ? null : String(tokenProp.value ?? ''),
        issueMarkersApplied: !markersProp.isNullObject && Boolean(markersProp.value),
        chunkToParagraphMapping,
      };
    });
  } catch (error) {
    console.error('Error reading custom document properties:', error);
    return { projectId: null, authToken: null, issueMarkersApplied: false, chunkToParagraphMapping: null };
  }
}

async function setIssueMarkersApplied(value: boolean): Promise<void> {
  if (typeof Word === 'undefined') return;

  await Word.run(async (context) => {
    const props = context.document.properties.customProperties;
    props.add('AIReviewer_IssueMarkersApplied', value);
    await context.sync();
  });
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
const severityOrder = [SeverityEnum.None, SeverityEnum.Low, SeverityEnum.Medium, SeverityEnum.High];
const severityColors: Record<string, string> = {
  [SeverityEnum.None]: '',
  [SeverityEnum.Low]: '#52aeff', // bg-blue-600
  [SeverityEnum.Medium]: '#cd8900', // bg-yellow-600
  [SeverityEnum.High]: '#f87274', // bg-red-600
};

export async function addIssueMarkers(issues: DocumentIssue[]): Promise<Map<number, DocumentIssue[]>> {
  if (typeof Word === 'undefined') return new Map();

  const issuesMap = await Word.run(async (context) => {
    const { chunkToParagraphMapping, issueMarkersApplied } = await getCustomDocumentProperties();
    if (!chunkToParagraphMapping) return new Map();

    const issuesMap = buildIssuesMap(issues, chunkToParagraphMapping);
    if (issueMarkersApplied) {
      return issuesMap;
    }

    const body = context.document.body;
    const paragraphs = body.paragraphs;
    paragraphs.load('items');
    await context.sync();

    for (const index of Array.from(issuesMap.keys())) {
      const issues = issuesMap.get(index) || [];
      if (index >= 0) {
        const paragraphSeverityIndex = issues.reduce(
          (max, issue) => Math.max(max, severityOrder.indexOf(issue.severity)),
          0,
        );
        const highlightColor = severityColors[severityOrder[paragraphSeverityIndex]] || '';
        if (highlightColor !== '') {
          const paragraph = paragraphs.items[index];
          if (!paragraph || paragraph.isNullObject) continue;
          const cc = paragraph.insertContentControl();
          cc.tag = `${MARKER_TAG}:${index}`;
          cc.title = `${issues.length} AI Reviewer Issues`;
          cc.appearance = 'BoundingBox';
          cc.color = highlightColor;
        }
      }
    }
    await context.sync();

    return issuesMap;
  });

  await setIssueMarkersApplied(true);

  return issuesMap;
}
