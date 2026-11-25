# Contributing to BloomClipping

Bug reports, ideas and pull requests are welcome.

- **Report a problem:** use *Report a problem* inside the app (it writes a clear report) or open a GitHub issue.
- **Pull requests:** keep one change per pull request, add or update a test in `tests/`, and run
  `python -m unittest discover -s tests -p "test_*.py"` before sending it.
- **Licence:** BloomClipping is licensed under the **AGPL-3.0** (see `LICENSE` and `NOTICE`). By sending a pull request you agree
  to the [Contributor License Agreement](CLA.md). Add this line to your pull request description:

  > I have read the BloomClipping CLA and I agree to it.

- **Other people's code:** only include code whose licence allows it (MIT, BSD, Apache-2.0 or AGPL-3.0-compatible), keep its
  copyright notice, and add it to `NOTICE`.
- **Files:** `.gitignore` is a whitelist. A new `.js`, `.css` or asset file needs a `!filename` line there, or it is left out.
