import { TestCase } from '../types';
import { formatIncEx } from '../util';

interface TestConfigurationSectionProps {
  testCase: TestCase;
}

export function TestConfigurationSection({ testCase }: TestConfigurationSectionProps) {
  return (
    <div>
      <h4 className="font-medium mb-3">Test Configuration</h4>
      <div className="bg-muted/30 p-3 rounded-lg">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="font-medium text-sm">Agent:</span>
              <span className="text-sm text-muted-foreground">{testCase.agent_test_case.agent.name}</span>
            </div>
            <div className="flex justify-between">
              <span className="font-medium text-sm">Run Count:</span>
              <span className="text-sm text-muted-foreground">
                {testCase.agent_test_case.evaluation_config.run_count}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="font-medium text-sm">Evaluator Model:</span>
              <span className="text-sm text-muted-foreground">
                {testCase.agent_test_case.evaluation_config.evaluator_model}
              </span>
            </div>
          </div>
          <div className="space-y-2">
            <div>
              <span className="font-medium text-sm">Strict Fields:</span>
              <div className="mt-1 text-sm text-muted-foreground wrap-break-word bg-background p-2 rounded border max-h-32 overflow-y-auto">
                <pre className="whitespace-pre-wrap font-mono text-xs">
                  {formatIncEx(testCase.agent_test_case.evaluation_config.strict_fields)}
                </pre>
              </div>
            </div>
          </div>
          <div className="space-y-2">
            <div>
              <span className="font-medium text-sm">LLM Fields:</span>
              <div className="mt-1 text-sm text-muted-foreground wrap-break-word bg-background p-2 rounded border max-h-32 overflow-y-auto">
                <pre className="whitespace-pre-wrap font-mono text-xs">
                  {formatIncEx(testCase.agent_test_case.evaluation_config.llm_fields)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
