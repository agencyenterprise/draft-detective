import { AnnotationView } from '@/components/annotate/annotation-view';

export default async function AnnotateSetPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <AnnotationView slug={slug} />;
}
