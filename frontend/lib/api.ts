import {
  AnalysisApi,
  Configuration,
  EvaluationApi,
  FeedbackApi,
  HealthApi,
  WorkflowsApi,
  Middleware,
} from './generated-api';
import { getSession } from 'next-auth/react';

export const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Middleware to add Bearer token to all requests
const authMiddleware: Middleware = {
  pre: async (context) => {
    const authHeader = await getAuthHeader();

    if (authHeader) {
      context.init.headers = {
        ...context.init.headers,
        Authorization: authHeader,
      };
    }
    return context;
  },
};

const config = new Configuration({
  basePath: apiUrl,
  middleware: [authMiddleware],
});

export const analysisApi = new AnalysisApi(config);
export const evaluationApi = new EvaluationApi(config);
export const feedbackApi = new FeedbackApi(config);
export const healthApi = new HealthApi(config);
export const workflowsApi = new WorkflowsApi(config);

export async function getAuthHeader(): Promise<string | undefined> {
  const session = await getSession();
  return session?.accessToken ? `Bearer ${session.accessToken}` : undefined;
}
