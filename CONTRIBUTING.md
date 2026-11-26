Contributions are welcome! Here's how you can help:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add some amazing feature'`
4. Push to the branch: git push origin feature/amazing-feature
5. Open a Pull Request

Before submitting your PR, please:

- Make sure your code follows the existing style
- Add/update tests as necessary
- Update documentation to reflect your changes
- Ensure all tests pass

## Releases

Pull requests target `dev`. Releases are cut by merging `dev` into `main`.

1. **Label your pull request.** Every pull request carries exactly one of `release:patch`, `release:minor`, `release:major` or `norelease`, and a required check enforces it. New pull requests get `release:patch` automatically. Change it if the work is a new feature (`minor`), a breaking change (`major`) or ships nothing on its own (`norelease`).
2. **The release pull request keeps itself up to date.** When `dev` has something `main` lacks, `release-pr.yml` opens a pull request from `dev` to `main`, or updates the open one. It's titled with the version merging it would release, lists the pull requests it brings and carries the largest of their labels. Change its label to override that, and later updates keep your choice.
3. **Merging it releases.** `release.yml` bumps the version in `pyproject.toml`, `uv.lock`, `frontend/package.json` and the plugin manifests (`.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`), writes the `CHANGELOG.md` entry with an LLM, commits both, tags the commit `vX.Y.Z` and publishes a GitHub Release with the same notes. It then merges `main` back into `dev`.

**Do not edit the version by hand.** The release commit sets it, and the release workflow refuses to run when `pyproject.toml` doesn't match the latest tag.

To cut a release without a pull request, or to preview one, run the **Release** workflow by hand from the Actions tab. It releases `main`'s current head and defaults to a dry run, which shows the version and changelog without pushing anything.

