# Third-party dependencies

Browser interaction uses the official [browser-use/browser-harness](https://github.com/browser-use/browser-harness), pinned to 0.1.13 (MIT). It is downloaded into each project's private runtime; upstream source and browser profiles are not bundled in this repository.

Local text extraction uses [pypdf](https://github.com/py-pdf/pypdf) (BSD-3-Clause), [python-docx](https://github.com/python-openxml/python-docx) (MIT), and [pylatexenc](https://github.com/phfaist/pylatexenc) (MIT). Dependencies retain their own licenses. See the installed distributions for their full license text.

On Python versions older than 3.12, the optional bootstrap downloads [Astral uv](https://github.com/astral-sh/uv) 0.12.23 (MIT/Apache-2.0), verifies its archive SHA-256, and installs a managed Python 3.12 runtime inside the project. No uv executable is added to PATH. The managed Python distribution retains its Python and bundled-component licenses.

The source archive includes this project's code and documentation only, not dependency binaries. A legacy Word converter, if used, is an existing local macOS textutil or LibreOffice installation.
