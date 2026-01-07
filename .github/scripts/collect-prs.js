#!/usr/bin/env node
/**
 * PR Collection Script - Multi-Level Traversal
 * 
 * Collects PRs by traversing commit history across N levels (configurable via MAX_DEPTH):
 * - Level 1: PRs merged to main
 * - Level 2: PRs merged to feature branches
 * - Level 3+: PRs merged to sub-feature branches
 * 
 * Usage:
 *   node collect-prs.js --from-tag v0.3.37 --to-tag v0.3.38
 *   node collect-prs.js --from-tag v0.3.37 --to-tag v0.3.38 --mock-mode
 */

const { execSync } = require('child_process');
const fs = require('fs');

// Configuration
const MERGE_PR_REGEX = /Merge pull request #(\d+) from/;
const MAX_DEPTH = 3;

/**
 * Extract PR numbers from commit messages
 */
function extractPRNumbers(commits) {
  const prNumbers = [];
  const lines = commits.split('\n');
  
  for (const line of lines) {
    const match = line.match(MERGE_PR_REGEX);
    if (match) {
      prNumbers.push(parseInt(match[1]));
    }
  }
  
  return prNumbers;
}

/**
 * Generic error handler for async operations
 */
async function withErrorHandling(fn, errorMessage, defaultValue = null) {
  try {
    return await fn();
  } catch (error) {
    console.error(`${errorMessage}: ${error.message}`);
    return defaultValue;
  }
}

/**
 * Get commits between two tags using git log
 * Uses --format=%s to get full commit subject lines (not truncated)
 */
function getCommitsBetweenTags(fromTag, toTag) {
  return withErrorHandling(
    () => execSync(`git log --format=%s ${fromTag}..${toTag}`, { encoding: 'utf-8' }),
    'Error getting commits',
    ''
  );
}

/**
 * Fetch PR commits from GitHub API
 */
async function fetchPRCommits(octokit, owner, repo, prNumber) {
  return withErrorHandling(
    async () => {
      const { data: commits } = await octokit.rest.pulls.listCommits({
        owner,
        repo,
        pull_number: prNumber,
        per_page: 100
      });
      return commits.map(c => c.commit.message).join('\n');
    },
    `Error fetching commits for PR #${prNumber}`,
    ''
  );
}

/**
 * Fetch PR details from GitHub API
 */
async function fetchPRDetails(octokit, owner, repo, prNumber) {
  return withErrorHandling(
    async () => {
      const { data: pr } = await octokit.rest.pulls.get({
        owner,
        repo,
        pull_number: prNumber
      });
      
      return {
        number: pr.number,
        title: pr.title,
        body: pr.body || '',
        author: pr.user.login,
        merged_at: pr.merged_at,
        base: pr.base.ref,
        labels: pr.labels.map(l => l.name)
      };
    },
    `Error fetching PR #${prNumber}`,
    null
  );
}

/**
 * Get PR numbers for a specific level
 */
async function getPRNumbersForLevel(level, previousLevelPRs, octokit, owner, repo, fromTag, toTag) {
  if (level === 1) {
    const commits = getCommitsBetweenTags(fromTag, toTag);
    return extractPRNumbers(commits);
  }
  
  // Level 2+: Get from commits in previous level's PRs
  const foundPRs = new Set();
  for (const prNum of previousLevelPRs) {
    const commits = await fetchPRCommits(octokit, owner, repo, prNum);
    const nums = extractPRNumbers(commits);
    nums.forEach(n => foundPRs.add(n));
  }
  return Array.from(foundPRs);
}

/**
 * Deduplicate and fetch PR details
 */
async function deduplicateAndFetchPRs(prNumbers, seenPRs, octokit, owner, repo, level) {
  const newPRs = [];
  const prDetails = [];
  
  for (const prNum of prNumbers) {
    if (seenPRs.has(prNum)) {
      console.log(`  PR #${prNum} already seen at higher level, skipping`);
      continue;
    }
    seenPRs.add(prNum);
    newPRs.push(prNum);
    
    const details = await fetchPRDetails(octokit, owner, repo, prNum);
    if (details) {
      prDetails.push({ ...details, level });
    }
  }
  
  return { newPRs, prDetails };
}

/**
 * Collect PRs with N-level traversal (configurable via MAX_DEPTH)
 * 
 * Deduplication strategy:
 * - seenPRs tracks all PR numbers encountered across all levels
 * - Each PR is only included once at its highest level (1 > 2 > 3...)
 * - This prevents double-counting when a PR is mentioned in multiple places
 * 
 * Example: If PR #100 is merged to feature branch (level 2) and that branch
 * is merged to main (level 1 merge commit), PR #100 only appears at level 1.
 */
async function collectPRsWithDepth(octokit, owner, repo, fromTag, toTag) {
  const prsByLevel = {};
  const seenPRs = new Set();
  const levelDescriptions = {
    1: 'main branch commits',
    2: 'feature branch PRs',
    3: 'sub-feature branch PRs'
  };
  
  // Initialize levels
  for (let i = 1; i <= MAX_DEPTH; i++) {
    prsByLevel[i] = [];
  }
  
  console.log(`\nStarting PR collection from ${fromTag} to ${toTag} (${MAX_DEPTH} levels)`);
  
  let previousLevelPRs = null;
  
  for (let level = 1; level <= MAX_DEPTH; level++) {
    const description = levelDescriptions[level] || `level ${level} PRs`;
    console.log(`\nLevel ${level}: Analyzing ${description}...`);
    
    const prNumbers = await getPRNumbersForLevel(level, previousLevelPRs, octokit, owner, repo, fromTag, toTag);
    const { newPRs, prDetails } = await deduplicateAndFetchPRs(prNumbers, seenPRs, octokit, owner, repo, level);
    
    prsByLevel[level].push(...prDetails);
    console.log(`Found ${newPRs.length} new PRs: ${newPRs.join(', ') || '(none)'}`);
    
    previousLevelPRs = newPRs;
    
    // Stop early if no new PRs found
    if (newPRs.length === 0) {
      console.log(`No new PRs at level ${level}, stopping traversal`);
      break;
    }
  }
  
  // Summary
  const total = Object.values(prsByLevel).reduce((sum, prs) => sum + prs.length, 0);
  console.log(`\nCollection complete: ${total} total PRs`);
  for (let i = 1; i <= MAX_DEPTH; i++) {
    console.log(`Level ${i}: ${prsByLevel[i].length}`);
  }
  
  return prsByLevel;
}

/**
 * Main execution
 */
async function main() {
  const args = process.argv.slice(2);
  const fromTag = args[args.indexOf('--from-tag') + 1];
  const toTag = args[args.indexOf('--to-tag') + 1];
  const mockMode = args.includes('--mock-mode');
  const outputFile = args[args.indexOf('--output') + 1] || null;
  
  if (!fromTag || !toTag) {
    console.error('Usage: node collect-prs.js --from-tag <tag> --to-tag <tag> [--mock-mode] [--output <file>]');
    process.exit(1);
  }
  
  if (mockMode) {
    console.log('MOCK MODE: Using test data');
    const mockData = {
      1: [{ number: 126, title: 'Release to main', level: 1, author: 'bot' }],
      2: [
        { number: 123, title: 'feat: Add AI validation', level: 2, author: 'dev1' },
        { number: 124, title: 'fix: Handle empty docs', level: 2, author: 'dev2' }
      ],
      3: [
        { number: 98, title: 'Implement validation logic', level: 3, author: 'dev1' }
      ]
    };
    
    if (outputFile) {
      fs.writeFileSync(outputFile, JSON.stringify(mockData, null, 2));
      console.log(`Mock data written to ${outputFile}`);
    } else {
      console.log(JSON.stringify(mockData, null, 2));
    }
    return;
  }
  
  // Real mode - requires GitHub token
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    console.error('Error: GITHUB_TOKEN environment variable not set');
    process.exit(1);
  }
  
  const { Octokit } = require('@octokit/rest');
  const octokit = new Octokit({ auth: token });
  
  // Extract owner/repo from git remote
  const remoteUrl = execSync('git config --get remote.origin.url', { encoding: 'utf-8' }).trim();
  const match = remoteUrl.match(/github\.com[:/](.+?)\/(.+?)(\.git)?$/);
  
  if (!match) {
    console.error('Error: Could not parse GitHub repository from remote URL');
    process.exit(1);
  }
  
  const [, owner, repo] = match;
  console.log(`\nRepository: ${owner}/${repo}`);
  
  const prsByLevel = await collectPRsWithDepth(octokit, owner, repo, fromTag, toTag);
  
  if (outputFile) {
    fs.writeFileSync(outputFile, JSON.stringify(prsByLevel, null, 2));
    console.log(`\nPR data written to ${outputFile}`);
  } else {
    console.log('\n' + JSON.stringify(prsByLevel, null, 2));
  }
}

// Run if executed directly
if (require.main === module) {
  main().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = { collectPRsWithDepth, extractPRNumbers };

