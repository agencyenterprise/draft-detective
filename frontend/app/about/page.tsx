import { Markdown } from '@/components/shared/markdown';
import { Card, CardContent } from '@/components/ui/card';
import { getAboutContentApiAboutGet } from '@/lib/generated-api';
import { createClient, createConfig } from '@/lib/generated-api/client';
import { serverApiUrl } from '@/lib/server-api-url';

const serverClient = createClient(createConfig({ baseUrl: serverApiUrl }));

export default async function AboutPage() {
  let content: string | null = null;

  try {
    const data = await getAboutContentApiAboutGet({ client: serverClient });
    content = data.value;
  } catch {
    // content stays null — error fallback rendered below
  }

  return (
    <Card className="max-w-5xl mx-auto">
      <CardContent>
        {content ? (
          <Markdown>{content}</Markdown>
        ) : (
          <p className="text-muted-foreground">Unable to load about content.</p>
        )}
      </CardContent>
    </Card>
  );
}
