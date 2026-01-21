import {
  createProjectEndpointApiProjectsPost,
  addFilesToProjectApiProjectProjectIdFilesPost,
  type ProjectDetailed,
  type File as FileModel,
} from '@/lib/generated-api';

class ProjectService {
  async createProject(mainDocument: File, title: string): Promise<ProjectDetailed> {
    return createProjectEndpointApiProjectsPost({
      body: {
        title,
        main_document: mainDocument,
      },
    });
  }

  async addFilesToProject(projectId: string, files: File[]): Promise<FileModel[]> {
    return addFilesToProjectApiProjectProjectIdFilesPost({
      path: { project_id: projectId },
      body: {
        files,
        role: 'support',
      },
    });
  }
}

export const projectService = new ProjectService();
