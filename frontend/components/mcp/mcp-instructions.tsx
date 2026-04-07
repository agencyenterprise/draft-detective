'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { baseUrl } from '@/lib/api';
import { Check, Copy, Server } from 'lucide-react';
import { useState } from 'react';

const mcpUrl = `${baseUrl}/mcp/`;

const tools = [
  { name: 'list_workflow_types', description: 'Lists all available workflow analysis types' },
  { name: 'create_project', description: 'Creates a project and ingests a markdown document' },
  { name: 'run_workflow', description: 'Runs one or more workflow analyses on a project and returns results' },
  { name: 'get_project', description: 'Retrieves full project details and workflow results by ID' },
];

const claudeCodeCommand = `claude mcp add-json "draft-detective" '{"type":"http","url":"${mcpUrl}"}'`;

export function McpInstructions() {
  const [copied, setCopied] = useState(false);
  const [copiedCommand, setCopiedCommand] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(mcpUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyCommand = async () => {
    await navigator.clipboard.writeText(claudeCodeCommand);
    setCopiedCommand(true);
    setTimeout(() => setCopiedCommand(false), 2000);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Server className="h-6 w-6" />
          MCP Server
        </h1>
        <p className="text-muted-foreground mt-1">
          Connect Draft Detective to Claude or any MCP-compatible client to run reviews directly from your AI assistant.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Your MCP Server URL</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded-md bg-muted px-3 py-2 text-sm font-mono break-all">{mcpUrl}</code>
            <Button variant="outline" onClick={handleCopy} title="Copy URL">
              {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
              {copied ? 'Copied' : 'Copy'}
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">
            Paste this URL when adding the integration in your MCP client.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Add via Claude Code CLI</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">Run this single command to add the MCP server to Claude Code:</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded-md bg-muted px-3 py-2 text-sm font-mono break-all">
              {claudeCodeCommand}
            </code>
            <Button variant="outline" onClick={handleCopyCommand} title="Copy command">
              {copiedCommand ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
              {copiedCommand ? 'Copied' : 'Copy'}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Available tools</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-3">
            {tools.map((tool) => (
              <li key={tool.name} className="flex flex-col gap-0.5">
                <code className="text-sm font-mono font-semibold">{tool.name}</code>
                <span className="text-sm text-muted-foreground">{tool.description}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
