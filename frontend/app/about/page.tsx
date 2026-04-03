import { Markdown } from '@/components/markdown';
import { Card, CardContent } from '@/components/ui/card';
import { getAppConfigApiAppConfigsKeyGet } from '@/lib/generated-api';
import { createClient, createConfig } from '@/lib/generated-api/client';

const serverClient = createClient(
  createConfig({ baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000' }),
);

export default async function AboutPage() {
  let content: string | null = null;

  try {
    const data = await getAppConfigApiAppConfigsKeyGet({
      client: serverClient,
      path: { key: 'about_page.content' },
    });
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
