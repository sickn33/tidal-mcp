# Attribution and provenance

This project started from the MIT-licensed `yuhuacheng/tidal-mcp` repository:

- https://github.com/yuhuacheng/tidal-mcp
- Original copyright: Yu Hua Cheng and contributors

TIDAL MCP retains the upstream MIT license and repository history. Its
implementation is substantially different: it uses the MCP Python SDK v2 over stdio,
does not run a Flask server, stores OAuth data outside temporary directories, and gates
remote writes behind a two-step approval flow.

The direct-call architecture and broader TIDAL API coverage in these community forks
were also useful references:

- https://github.com/ibeal/tidal-mcp
- https://github.com/dragomirweb/tidal-mcp

Those projects are MIT-licensed; no third-party OAuth client identifier or secret is
copied into this repository.

TIDAL is a trademark of its respective owner. This independent project is not affiliated with,
endorsed by, or sponsored by TIDAL. No TIDAL logo, album artwork, or recordings are bundled with
the project.
