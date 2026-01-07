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
const PR_BODY_EXCERPT_LENGTH = 300;

const LEVEL_CONFIG = {
  1: {
    title: 'Main Branch Merges',
    formatPR: (pr) => {
      let text = `\n#${pr.number} - ${pr.title}\n`;
      if (pr.body && pr.body.length > 0) {
        const excerpt = pr.body.substring(0, PR_BODY_EXCERPT_LENGTH);
        text += `Description: ${excerpt}${pr.body.length > PR_BODY_EXCERPT_LENGTH ? '...' : ''}\n`;
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
        text += `Description:\n${pr.body}\n`;
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
  let prompt = `You are a technical writer generating a changelog entry for version ${version} of an AI-powered document review system.

Based on the following pull requests organized by merge hierarchy, generate a concise, well-organized changelog entry.

`;

  // Add all level sections
  for (let level = 1; level <= 3; level++) {
    prompt += formatLevelSection(level, prsByLevel[level]);
  }

  prompt += `
INSTRUCTIONS:
1. Group changes into these categories (only include if applicable):
   - Added (new features)
   - Changed (changes in existing functionality)
   - Fixed (bug fixes)
   - Security (security improvements)
   - Deprecated (soon-to-be removed features)
   - Removed (removed features)

2. Focus on Level 2 PRs as the main content source
3. Use Level 1 for high-level structure
4. Use Level 3 for completeness and context
5. Write for end users, not developers
6. Be concise but informative
7. Highlight breaking changes if any exist
8. Use bullet points (- prefix)
9. DO NOT include version number or date in output
10. DO NOT add extra commentary or explanations

Generate the changelog entry now:`;

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
    console.log('\nPROMPT (first 500 chars):');
    console.log(prompt.substring(0, 500) + '...');
    console.log('');
  }
  
  const OpenAI = require('openai');
  const openai = new OpenAI({ apiKey });
  
  const response = await openai.chat.completions.create({
    model: 'gpt-5.2',
    messages: [
      {
        role: 'system',
        content: 'You are a technical writer specializing in software changelogs. You write clear, concise, and user-focused release notes.'
      },
      {
        role: 'user',
        content: prompt
      }
    ],
    temperature: 0.3,
    max_tokens: 1500
  });
  
  const changelog = response.choices[0].message.content.trim();
  
  console.log(`Changelog generated (${changelog.length} characters)`);
  console.log(`Tokens used: ${response.usage.total_tokens}`);
  console.log(`Estimated cost: $${(response.usage.total_tokens * 0.000005).toFixed(4)}`);
  
  return changelog;
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

