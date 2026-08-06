{
  description = "nvim-mcp - MCP server for AI-assisted control of Neovim via msgpack-RPC";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    self,
    nixpkgs,
    pyproject-nix,
    uv2nix,
    pyproject-build-systems,
  }: let
    inherit (nixpkgs) lib;

    systems = ["x86_64-linux" "aarch64-linux"];
    forAllSystems = lib.genAttrs systems;
    pkgsFor = system: nixpkgs.legacyPackages.${system};

    pyproject = lib.importTOML ./pyproject.toml;

    # Resolve dependencies from uv.lock rather than nixpkgs' python3Packages.
    # nixpkgs cannot express this dependency set at all: mcp 2.x pulls in
    # httpx2, httpcore2, mcp-types, annotated-doc and starlette 1.x, none of
    # which are packaged, and python3Packages.mcp is still on 1.x.
    workspace = uv2nix.lib.workspace.loadWorkspace {workspaceRoot = ./.;};

    # Prefer published wheels; the transitive set includes cryptography,
    # pydantic-core and rpds-py, which are expensive to build from sdist.
    # All of them ship manylinux wheels for every supported system.
    overlay = workspace.mkPyprojectOverlay {sourcePreference = "wheel";};

    mkPythonSet = pkgs:
      (pkgs.callPackage pyproject-nix.build.packages {python = pkgs.python313;}).overrideScope
      (lib.composeManyExtensions [
        pyproject-build-systems.overlays.wheel
        overlay
      ]);

    mkPackage = pkgs: let
      pythonSet = mkPythonSet pkgs;
      inherit (pkgs.callPackages pyproject-nix.build.util {}) mkApplication;
      venv = pythonSet.mkVirtualEnv "nvim-mcp-env" workspace.deps.default;
    in
      (mkApplication {
        inherit venv;
        package = pythonSet.nvim-mcp;
      }).overrideAttrs (old: {
        # Stands in for buildPythonApplication's pythonImportsCheck. Importing
        # the server module resolves the mcp API surface actually used, so a
        # dependency set that no longer matches the code fails the build here
        # rather than at runtime.
        postInstall =
          (old.postInstall or "")
          + ''
            ${venv}/bin/python -c "import nvim_mcp.server"
          '';

        meta =
          (old.meta or {})
          // {
            description = pyproject.project.description;
            homepage = "https://github.com/paulburgess1357/nvim-mcp";
            license = lib.licenses.mit;
            mainProgram = "nvim-mcp";
            platforms = lib.platforms.linux;
          };
      });
  in {
    packages = forAllSystems (system: {
      default = mkPackage (pkgsFor system);
      nvim-mcp = mkPackage (pkgsFor system);
    });

    apps = forAllSystems (system: {
      default = {
        type = "app";
        program = "${self.packages.${system}.default}/bin/nvim-mcp";
      };
    });

    devShells = forAllSystems (system: let
      pkgs = pkgsFor system;
    in {
      default = pkgs.mkShell {
        packages = [
          pkgs.uv
          pkgs.python3
        ];
        shellHook = ''
          echo "nvim-mcp dev shell (uv $(uv --version 2>/dev/null | cut -d' ' -f2))"
          echo "  uv sync          # install deps"
          echo "  uv run nvim-mcp  # run the server"
        '';
      };
    });

    formatter = forAllSystems (system: (pkgsFor system).nixpkgs-fmt);
  };
}
