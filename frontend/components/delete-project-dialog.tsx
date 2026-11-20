import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { deleteProjectEndpointApiProjectProjectIdDelete } from '@/lib/generated-api';
import { PROJECT_LIST_QUERY_KEY } from '@/lib/hooks/use-project-data';
import { useToastMutation } from '@/lib/hooks/use-toast-mutation';
import { useQueryClient } from '@tanstack/react-query';
import { Trash2 } from 'lucide-react';

interface DeleteProjectDialogProps {
  projectId: string;
  projectTitle: string;
}

export function DeleteProjectDialog({ projectId, projectTitle }: DeleteProjectDialogProps) {
  const queryClient = useQueryClient();

  const deleteMutation = useToastMutation({
    mutationFn: () => deleteProjectEndpointApiProjectProjectIdDelete({ path: { project_id: projectId } }),
    successMessage: 'Project deleted successfully',
    errorMessage: 'Failed to delete project',
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PROJECT_LIST_QUERY_KEY });
    },
  });

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="outline" size="sm" className="text-destructive hover:bg-destructive/10">
          <Trash2 className="h-4 w-4" />
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Project?</AlertDialogTitle>
          <AlertDialogDescription>
            This will permanently delete the project <strong>{projectTitle}</strong> and all associated results. This
            action cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={() => deleteMutation.mutate()}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
