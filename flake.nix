{
  description = "nixpick — recherche nixpkgs et édition de environment.systemPackages";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
    in
    {
      packages.${system}.default = pkgs.python3Packages.buildPythonApplication {
        pname = "nixpick";
        version = "0.3.2";
        pyproject = true;
        src = ./.;
        nativeBuildInputs = with pkgs.python3Packages; [
          setuptools
          wheel
        ];
        propagatedBuildInputs = with pkgs.python3Packages; [
          textual
          rich
        ];
        doCheck = false;
      };

      apps.${system}.default = {
        type = "app";
        program = "${self.packages.${system}.default}/bin/nixpick";
      };

      formatter.${system} = pkgs.nixpkgs-fmt;
    };
}
