"""Nexar Design API renderer.

Hits the Nexar `design.domain` GraphQL API to render a PCB design from an
Altium 365 workspace. Outputs:

  - GLB (3D model) for the PCB variant
  - JSON dump of PCB primitives (pads, tracks, vias, layer stack, outline)
    suitable for reconstructing the geometry the OpenTK demo renders.

IMPORTANT — API SCOPE:
  This requires a Nexar app registered with the **`design.domain`** scope.
  The existing electronics-stack supply-chain client uses `supply.domain` —
  these are *different scopes*. To enable design rendering:

    1. Go to https://portal.nexar.com -> your app -> Permissions
    2. Add the `design.domain` scope and accept the developer agreement
    3. (Token cache will refresh automatically on next call)

  If the user has only Supply scope, this script returns a clear error.

INPUTS:
  - workspace url + project id (Altium 365)
  - OR project id alone (lookup default workspace)

OUTPUTS:
  - <out_dir>/<project>.glb        (3D mesh, if available)
  - <out_dir>/<project>.pcb.json   (primitive dump)
  - <out_dir>/<project>.meta.json  (project metadata + scope info)

KICAD NOTE:
  The Nexar Design API does NOT accept KiCad project uploads. The Altium 365
  workspace is the authoritative source. To render KiCad designs, you'd need
  to either:
    (a) push the design to Altium 365 (Altium Designer round-trip), or
    (b) use a different toolchain (kicad-cli pcb export step / glb).
  This wrapper covers case (a). For case (b) see scripts/kicad_render.py
  (TODO; kicad-cli supports `pcb export step` and `pcb export glb`).
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

CONFIG_DIR = Path.home() / ".config" / "electronics-stack"
CACHE_DIR = Path.home() / ".cache" / "electronics-stack" / "nexar_design"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = CONFIG_DIR / ".env"
TOKEN_FILE = CACHE_DIR / "token.json"

TOKEN_URL = "https://identity.nexar.com/connect/token"
GRAPHQL_URL = "https://api.nexar.com/graphql"
DESIGN_SCOPE = "design.domain"


def load_env() -> dict:
    env = dict(os.environ)
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


class NexarDesignClient:
    """GraphQL client for the Nexar `design.domain` scope.

    Independent token cache from octopart_client because the scope differs.
    """

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: dict | None = None
        self._load_token()

    @classmethod
    def from_env(cls) -> "NexarDesignClient":
        env = load_env()
        cid = env.get("NEXAR_CLIENT_ID")
        sec = env.get("NEXAR_CLIENT_SECRET")
        if not cid or not sec:
            raise RuntimeError(
                f"NEXAR_CLIENT_ID/SECRET not set. Add to {ENV_FILE}.\n"
                f"Required scope: {DESIGN_SCOPE} (Supply-only apps will fail)."
            )
        return cls(cid, sec)

    def _load_token(self) -> None:
        if TOKEN_FILE.exists():
            try:
                t = json.loads(TOKEN_FILE.read_text())
                if t.get("expires_at", 0) > time.time() + 30 and t.get("scope") == DESIGN_SCOPE:
                    self._token = t
            except Exception:
                pass

    def _refresh(self) -> None:
        r = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": DESIGN_SCOPE,
            },
            timeout=15,
        )
        if r.status_code != 200:
            try:
                body = r.json()
            except Exception:
                body = {"raw": r.text}
            raise RuntimeError(
                f"Nexar token refresh failed (status={r.status_code}): {body}\n"
                f"Most common cause: Nexar app does not have the `{DESIGN_SCOPE}` scope.\n"
                f"Go to https://portal.nexar.com -> your app -> Permissions, add {DESIGN_SCOPE}."
            )
        body = r.json()
        body["expires_at"] = time.time() + int(body.get("expires_in", 1800))
        body["scope"] = DESIGN_SCOPE
        self._token = body
        TOKEN_FILE.write_text(json.dumps(body))
        try:
            TOKEN_FILE.chmod(0o600)
        except Exception:
            pass

    def _headers(self) -> dict:
        if not self._token or self._token.get("expires_at", 0) < time.time() + 30:
            self._refresh()
        return {
            "Authorization": f"Bearer {self._token['access_token']}",
            "Content-Type": "application/json",
        }

    def query(self, gql: str, variables: dict | None = None) -> dict:
        r = requests.post(
            GRAPHQL_URL,
            headers=self._headers(),
            json={"query": gql, "variables": variables or {}},
            timeout=60,
        )
        r.raise_for_status()
        out = r.json()
        if "errors" in out:
            raise RuntimeError(f"GraphQL errors: {out['errors']}")
        return out

    # --- queries (mirrored from Nexar.Client/Resources/Queries.graphql) ---

    Q_WORKSPACES = """
    query GetWorkspaces {
      desWorkspaces {
        id url name description isDefault
        location { name apiServiceUrl filesServiceUrl }
      }
    }
    """

    Q_PROJECTS = """
    query GetProjects($workspaceUrl: String!, $cursor: String) {
      desProjects(workspaceUrl: $workspaceUrl, after: $cursor) {
        totalCount
        nodes { id name description projectId previewUrl updatedAt }
        pageInfo { endCursor hasNextPage }
      }
    }
    """

    Q_GLB = """
    query Get3DModel($id: ID!) {
      desProjectById(id: $id) {
        id name description
        design { variants { pcb { mesh3D { glbFile { fileName downloadUrl } } } } }
      }
    }
    """

    Q_PCB = """
    query GetPcbModel($id: ID!) {
      desProjectById(id: $id) {
        id name description
        design { variants { pcb {
          documentId documentName
          layerStack { stacks { name layers {
            name thickness { xMm } dielectricConstant copperWeight { gram }
            layerType layerProperties { name text size { xMm } }
          } } }
          outline { vertices { xMm yMm } }
          pads { designator globalDesignator padType shape
                 net { name } layer { name }
                 position { xMm yMm } rotation
                 size { xMm yMm } holeSize { xMm } }
          nets {
            name
            pads { designator globalDesignator padType shape
                   layer { name } position { xMm yMm } rotation
                   size { xMm yMm } holeSize { xMm } }
            tracks { layer { name } width { xMm }
                     begin { xMm yMm } end { xMm yMm } }
            vias { shape beginLayer { name } endLayer { name }
                   position { xMm yMm }
                   padDiameter { xMm } holeDiameter { xMm } }
          }
        } } }
      }
    }
    """

    def workspaces(self) -> list[dict]:
        return self.query(self.Q_WORKSPACES)["data"]["desWorkspaces"]

    def projects(self, workspace_url: str) -> list[dict]:
        all_nodes: list[dict] = []
        cursor: str | None = None
        while True:
            d = self.query(self.Q_PROJECTS, {"workspaceUrl": workspace_url, "cursor": cursor})["data"]
            page = d["desProjects"]
            all_nodes.extend(page.get("nodes", []) or [])
            if not page["pageInfo"]["hasNextPage"]:
                break
            cursor = page["pageInfo"]["endCursor"]
        return all_nodes

    def glb_url(self, project_id: str) -> dict | None:
        d = self.query(self.Q_GLB, {"id": project_id})["data"]["desProjectById"]
        try:
            return d["design"]["variants"][0]["pcb"]["mesh3D"]["glbFile"]
        except (KeyError, TypeError, IndexError):
            return None

    def pcb_primitives(self, project_id: str) -> dict:
        d = self.query(self.Q_PCB, {"id": project_id})["data"]["desProjectById"]
        return d


# --- top-level CLI render ---

def render(
    project_id: str | None,
    out_dir: Path,
    workspace_url: str | None = None,
    project_name: str | None = None,
    download_glb: bool = True,
    dump_primitives: bool = True,
) -> dict:
    """Render a PCB design.

    Resolves project_id by name if `project_name` is given. Writes:
      <out_dir>/<slug>.glb (if available)
      <out_dir>/<slug>.pcb.json (primitive dump)
      <out_dir>/<slug>.meta.json (provenance)
    """
    out_dir = Path(out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    client = NexarDesignClient.from_env()

    # resolve workspace + project
    workspaces = client.workspaces()
    if not workspaces:
        raise RuntimeError("No Altium 365 workspaces visible to this Nexar app. "
                           "User must be a member of at least one A365 workspace.")
    if not workspace_url:
        ws = next((w for w in workspaces if w.get("isDefault")), workspaces[0])
        workspace_url = ws["url"]

    if not project_id:
        if not project_name:
            raise RuntimeError("Pass --project-id or --project-name.")
        projects = client.projects(workspace_url)
        match = next((p for p in projects if p.get("name") == project_name), None)
        if not match:
            raise RuntimeError(
                f"Project '{project_name}' not found in {workspace_url}. "
                f"Available: {[p.get('name') for p in projects]}"
            )
        project_id = match["id"]
        slug = (match["name"] or "design").replace(" ", "_")
    else:
        slug = project_id.replace("/", "_")

    result: dict = {"project_id": project_id, "workspace_url": workspace_url, "files": {}}

    if download_glb:
        glb_meta = client.glb_url(project_id)
        if glb_meta and glb_meta.get("downloadUrl"):
            url = glb_meta["downloadUrl"]
            target = out_dir / f"{slug}.glb"
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            target.write_bytes(r.content)
            result["files"]["glb"] = str(target)
            result["glb_filename"] = glb_meta.get("fileName")
        else:
            result["files"]["glb"] = None
            result["glb_note"] = "No 3D mesh available for this PCB variant."

    if dump_primitives:
        prim = client.pcb_primitives(project_id)
        target = out_dir / f"{slug}.pcb.json"
        target.write_text(json.dumps(prim, indent=2))
        result["files"]["pcb_json"] = str(target)

    meta = out_dir / f"{slug}.meta.json"
    meta.write_text(json.dumps(result, indent=2))
    result["files"]["meta"] = str(meta)
    return result


def main():
    ap = argparse.ArgumentParser(description="Render a PCB via the Nexar Design API.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s_ws = sub.add_parser("workspaces", help="List visible Altium 365 workspaces.")
    s_pr = sub.add_parser("projects", help="List projects in a workspace.")
    s_pr.add_argument("--workspace-url", help="Workspace URL (default: default workspace).")

    s_rd = sub.add_parser("render", help="Download GLB + dump PCB primitives.")
    s_rd.add_argument("--project-id", help="Nexar project ID.")
    s_rd.add_argument("--project-name", help="Lookup project by name (uses default workspace unless --workspace-url).")
    s_rd.add_argument("--workspace-url", help="Workspace URL.")
    s_rd.add_argument("--out", default=".", help="Output directory.")
    s_rd.add_argument("--no-glb", action="store_true")
    s_rd.add_argument("--no-primitives", action="store_true")

    args = ap.parse_args()
    try:
        client = NexarDesignClient.from_env()
        if args.cmd == "workspaces":
            print(json.dumps(client.workspaces(), indent=2))
            return
        if args.cmd == "projects":
            ws_url = args.workspace_url
            if not ws_url:
                wss = client.workspaces()
                ws_url = next((w for w in wss if w.get("isDefault")), wss[0])["url"] if wss else None
            if not ws_url:
                print("ERROR: no workspaces available", file=sys.stderr)
                sys.exit(2)
            print(json.dumps(client.projects(ws_url), indent=2))
            return
        if args.cmd == "render":
            out = render(
                project_id=args.project_id,
                out_dir=Path(args.out),
                workspace_url=args.workspace_url,
                project_name=args.project_name,
                download_glb=not args.no_glb,
                dump_primitives=not args.no_primitives,
            )
            print(json.dumps(out, indent=2))
            return
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
