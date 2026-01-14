Perform a comprehensive code review by examining the diff between the current branch and the `dev` branch.

Evaluate quality, maintainability, correctness, and style. Explain your reasoning before providing conclusions or recommendations.

Consider edge cases, security implications, documentation gaps, and test coverage when relevant.

Order your comments starting with the most severe items first.

Return only your comments using conventional code-review formatting (https://conventionalcomments.org/). Each comment must begin with the comment number followed by the file name and the affected line or line range, for example:

<example>
# Comment #1

`frontend/app/(authenticated)/tools/reference-downloader/components/reference-downloader-tool.tsx` 150-152

severity: [high, medium, low]
issue: Typo in the sentence
suggestion: Change the sentence to be grammatically correct
</example>