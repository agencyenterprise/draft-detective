import { useShare } from '@/context/share-context';
import Link from 'next/link';
import { ComponentProps } from 'react';

interface FileDownloadLinkProps extends Omit<ComponentProps<typeof Link>, 'href' | 'target'> {
  fileId: string;
}

/**
 * A link component that points to the file download endpoint.
 * Opens in a new tab by default.
 */
export function FileDownloadLink({ fileId, children, ...props }: FileDownloadLinkProps) {
  const { shareToken } = useShare();

  const href = shareToken ? `/api/files/download/${fileId}?share_token=${shareToken}` : `/api/files/download/${fileId}`;

  return (
    <Link href={href} target="_blank" {...props}>
      {children}
    </Link>
  );
}
