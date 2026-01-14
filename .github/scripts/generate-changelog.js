#!/usr/bin/env node
/**
 * AI Changelog Generator
 * 
 * Uses OpenAI GPT-4o to generate human-readable changelog entries
 * from PR data collected by collect-prs.js
 * 
 * Usage:
 *   node generate-changelog.js --pr-data prs.json --version 0.3.38
 *   node generate-changelog.js --pr-data prs.json --version 0.3.38 --output changelog.md
 */

const fs = require('fs');

// Configuration
const PR_BODY_MAX_LENGTH = 4000;

const LEVEL_CONFIG = {
  1: {
    title: 'Main Branch Merges',
    formatPR: (pr) => {
      let text = `\n#${pr.number} - ${pr.title}\n`;
      if (pr.body && pr.body.length > 0) {
        const excerpt = pr.body.substring(0, PR_BODY_MAX_LENGTH);
        text += `Description: ${excerpt}${pr.body.length > PR_BODY_MAX_LENGTH ? '...' : ''}\n`;
      }
      return text;
    }
  },
  2: {
    title: 'Feature Branch PRs (PRIMARY SOURCE)',
    formatPR: (pr) => {
      let text = `\n#${pr.number} - ${pr.title}\n`;
      text += `Author: ${pr.author}\n`;
      if (pr.labels && pr.labels.length > 0) {
        text += `Labels: ${pr.labels.join(', ')}\n`;
      }
      if (pr.body) {
        const excerpt = pr.body.substring(0, PR_BODY_MAX_LENGTH);
        text += `Description:\n${excerpt}${pr.body.length > PR_BODY_MAX_LENGTH ? '...' : ''}\n`;
      }
      return text;
    }
  },
  3: {
    title: 'Implementation PRs (Supporting Context)',
    formatPR: (pr) => `#${pr.number} - ${pr.title} (by ${pr.author})\n`
  }
};

/**
 * Format PRs for a specific level
 */
function formatLevelSection(level, prs) {
  if (!prs || prs.length === 0) return '';
  
  const config = LEVEL_CONFIG[level];
  if (!config) return '';
  
  let section = `=== LEVEL ${level}: ${config.title} ===\n`;
  for (const pr of prs) {
    section += config.formatPR(pr);
  }
  return section + '\n';
}

/**
 * Build hierarchical prompt for OpenAI
 */
function buildPrompt(prsByLevel, version) {
  let prompt = `Generate a changelog entry for version ${version} based ONLY on the pull request data provided below.

`;

  // Add all level sections
  for (let level = 1; level <= 3; level++) {
    prompt += formatLevelSection(level, prsByLevel[level]);
  }

  prompt += `
CRITICAL REQUIREMENTS:
1. ONLY include changes that are EXPLICITLY stated in the PR titles and descriptions above
2. DO NOT infer, assume, or hallucinate any details not present in the data
3. DO NOT invent file paths, function names, or technical implementation details
4. If a PR description is vague, use the PR title as-is or summarize at a high level
5. When in doubt, keep descriptions general rather than fabricating specifics

OUTPUT FORMAT:
- Group into categories: Added, Changed, Fixed, Security, Deprecated, Removed (only include categories with items)
- Use bullet points (- prefix)
- Each bullet should be a single concise sentence
- DO NOT include version number or date
- DO NOT add commentary or explanations outside the bullets

PRIORITY:
- Level 2 PRs are the primary source of truth
- Level 1 provides merge context
- Level 3 provides implementation details

Generate the changelog now:`;

  return prompt;
}

/**
 * Generate changelog using OpenAI
 */
async function generateChangelog(prsByLevel, version, apiKey) {
  console.log('\nGenerating changelog with AI...');
  
  const prompt = buildPrompt(prsByLevel, version);
  
  // Log prompt for debugging
  if (process.env.DEBUG) {
    console.log('\n======================================== FULL PROMPT SENT TO AI ========================================');
    console.log(prompt);
    console.log('========================================================================================================\n');
  }
  
  try {
    const OpenAI = require('openai');
    const openai = new OpenAI({ apiKey });
    
    const response = await openai.chat.completions.create({
      model: 'gpt-4o',
      messages: [
        {
          role: 'system',
          content: `You are a precise changelog generator. Your task is to accurately summarize software changes based ONLY on the provided pull request titles and descriptions.

STRICT RULES:
- ONLY use information explicitly stated in the PR titles and descriptions
- NEVER invent file paths, function names, class names, or technical implementation details
- NEVER assume or hallucinate what code was changed or how
- If a PR description is vague or missing, use the PR title verbatim
- Keep descriptions at the same level of detail as the source PR data
- When in doubt, be general rather than specific`
        },
        {
          role: 'user',
          content: prompt
        }
      ],
      temperature: 0,
      max_tokens: 2000
    });
  
    const changelog = response.choices[0].message.content.trim();
    
    console.log(`Changelog generated (${changelog.length} characters)`);
    console.log(`Tokens used: ${response.usage.total_tokens}`);
    console.log(`Estimated cost: $${(response.usage.total_tokens * 0.000005).toFixed(4)}`);
    
    return changelog;
  } catch (error) {
    console.error('Error calling OpenAI API:', error.message);
    console.log('Falling back to basic changelog generation');
    return generateFallbackChangelog(prsByLevel);
  }
}

/**
 * Fallback changelog generation (no AI)
 */
function generateFallbackChangelog(prsByLevel) {
  const categories = {
    Added: [],
    Changed: [],
    Fixed: []
  };
  
  // Categorize PRs based on title keywords
  for (const level of [1, 2, 3]) {
    for (const pr of prsByLevel[level] || []) {
      const title = pr.title.toLowerCase();
      
      if (title.includes('feat') || title.includes('add')) {
        categories.Added.push(`- ${pr.title.replace(/^(feat|feature):\s*/i, '')}`);
      } else if (title.includes('fix')) {
        categories.Fixed.push(`- ${pr.title.replace(/^fix:\s*/i, '')}`);
      } else {
        categories.Changed.push(`- ${pr.title}`);
      }
    }
  }
  
  let changelog = '';
  
  for (const [category, items] of Object.entries(categories)) {
    if (items.length > 0) {
      changelog += `### ${category}\n\n`;
      changelog += items.join('\n') + '\n\n';
    }
  }
  
  return changelog.trim();
}

/**
 * Main execution
 */
async function main() {
  const args = process.argv.slice(2);
  const prDataFile = args[args.indexOf('--pr-data') + 1];
  const version = args[args.indexOf('--version') + 1];
  const outputFile = args[args.indexOf('--output') + 1] || null;
  
  if (!prDataFile || !version) {
    console.error('Usage: node generate-changelog.js --pr-data <file> --version <version> [--output <file>]');
    process.exit(1);
  }
  
  // Read PR data
  const prsByLevel = JSON.parse(fs.readFileSync(prDataFile, 'utf-8'));
  
  // Get OpenAI API key
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    console.error('Error: OPENAI_API_KEY environment variable not set');
    process.exit(1);
  }
  
  // Generate changelog
  const changelog = await generateChangelog(prsByLevel, version, apiKey);
  
  if (outputFile) {
    fs.writeFileSync(outputFile, changelog);
    console.log(`\nChangelog written to ${outputFile}`);
  } else {
    console.log('\nGENERATED CHANGELOG:');
    console.log('----------------------------------------');
    console.log(changelog);
    console.log('----------------------------------------');
  }
}

// Run if executed directly
if (require.main === module) {
  main().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = { generateChangelog, buildPrompt };

