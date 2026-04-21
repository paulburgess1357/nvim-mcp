{
  description = "nvim-mcp - MCP server for AI-assisted control of Neovim via msgpack-RPC";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      pkgsFor = system: nixpkgs.legacyPackages.${system};

      pyproject = nixpkgs.lib.importTOML ./pyproject.toml;

      mkPackage = pkgs:
        pkgs.python3Packages.buildPythonApplication {
          pname = pyproject.project.name;
          version = pyproject.project.version;
          pyproject = true;

          src = pkgs.lib.fileset.toSource {
            root = ./.;
            fileset = pkgs.lib.fileset.unions [
              ./pyproject.toml
              ./README.md
              ./LICENSE
              ./src
            ];
          };

          build-system = [ pkgs.python3Packages.hatchling ];

          dependencies = with pkgs.python3Packages; [
            mcp
            msgpack
          ] ++ pkgs.python3Packages.mcp.optional-dependencies.cli;

          pythonImportsCheck = [ "nvim_mcp" ];

          doCheck = false;

          meta = {
            description = pyproject.project.description;
            homepage = "https://github.com/paulburgess1357/nvim-mcp";
            license = pkgs.lib.licenses.mit;
            mainProgram = "nvim-mcp";
            platforms = pkgs.lib.platforms.linux;
          };
        };
    in
    {
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

      devShells = forAllSystems (system:
        let pkgs = pkgsFor system; in {
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
