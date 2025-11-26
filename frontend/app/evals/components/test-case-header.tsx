import { Badge } from '@/components/ui/badge';
import { ChevronDown, ChevronRight, Clock } from 'lucide-react';
import { TestCase } from '../types';
import { formatDuration } from '../util';
import { cn } from '@/lib/utils';
import { percentageFormatter } from '../formatters';

interface TestCaseHeaderProps {
  name: string;
  testCases: TestCase[];
  accuracy: number;
  isExpanded: boolean;
  onToggle: () => void;
}

export function TestCaseHeader({ name, testCases, accuracy, isExpanded, onToggle }: TestCaseHeaderProps) {
  return (
    <div className="cursor-pointer px-4 py-2" onClick={onToggle}>
      <div className="space-y-2">
        <div className="flex items-center gap-2 justify-between">
          <div className="flex items-center gap-2 ">
            {isExpanded ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )}
            <p className="text-sm font-medium flex items-center gap-2">{name}</p>
          </div>
          <Badge
            variant={accuracy >= 0.8 ? 'success' : accuracy >= 0.6 ? 'secondary' : 'destructive'}
            className="self-end"
          >
            {percentageFormatter.format(accuracy)} accuracy
          </Badge>
        </div>

        <div className="space-y-2 pl-6">
          {testCases.map((testCase) => (
            <div key={testCase.nodeid} className="flex gap-1 items-center">
              <p className="text-xs text-muted-foreground wrap-anywhere">{testCase.nodeid}</p>
              <span
                className={cn(
                  'text-xs px-1 py-0.5 w-12 text-center rounded-md',
                  testCase.outcome === 'passed' ? 'text-green-600 bg-green-500/10' : 'text-red-600 bg-red-500/10',
                )}
              >
                {testCase.outcome === 'passed' ? 'Passed' : 'Failed'}
              </span>
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                {formatDuration(testCase.call.duration)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
