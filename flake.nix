{
  description = "nixpick — recherche nixpkgs et édition de environment.systemPackages";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      # opentui/yoga-python ne publient que des wheels cp312/cp313 : le
      # python3Packages par défaut (3.14) n'a pas de wheel, on fige 3.13.
      python = pkgs.python313Packages;

      yoga-python = python.buildPythonPackage {
        pname = "yoga-python";
        version = "0.1.5";
        format = "wheel";
        src = pkgs.fetchurl {
          url = "https://files.pythonhosted.org/packages/8d/d0/cdd84b2e05eafa9e9a705ba3075b3ecdfe87db844ca7d2c6a4b7e3cde221/yoga_python-0.1.5-cp313-cp313-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl";
          hash = "sha256-3mgMfmD0NUkZOyPW6dn52xhCXr/ZeGsGU04ytLH3Gdw=";
        };
        nativeBuildInputs = [ pkgs.autoPatchelfHook ];
        buildInputs = [ pkgs.stdenv.cc.cc.lib ];
      };

      opentui = python.buildPythonPackage {
        pname = "opentui";
        version = "0.1.2";
        format = "wheel";
        src = pkgs.fetchurl {
          url = "https://files.pythonhosted.org/packages/44/55/f31ec925663dcffc4c303acbd29c2ba80055f6870ec1b24091f00f08f336/opentui-0.1.2-cp313-cp313-manylinux_2_28_x86_64.whl";
          hash = "sha256-srdO3OCE0N7NQw98erPwuNKGn/Kv5krBd9xj2vkUY60=";
        };
        nativeBuildInputs = [ pkgs.autoPatchelfHook ];
        buildInputs = [ pkgs.stdenv.cc.cc.lib ];
        propagatedBuildInputs = [ yoga-python ];
      };

      nixpick = python.buildPythonApplication {
        pname = "nixpick";
        version = "0.5.0";
        pyproject = true;
        src = ./.;
        nativeBuildInputs = with python; [
          setuptools
          wheel
        ] ++ [ pkgs.installShellFiles ];
        propagatedBuildInputs = [ opentui ];
        postInstall = ''
          installShellCompletion --cmd nixpick \
            --bash ${./assets/completions/nixpick.bash} \
            --fish ${./assets/completions/nixpick.fish} \
            --zsh ${./assets/completions/_nixpick}
        '';
        nativeCheckInputs = with python; [ pytestCheckHook ] ++ [ pkgs.git ];
        checkInputs = [ python.pytest opentui ];
        doCheck = true;
        preCheck = ''
          export PATH="${pkgs.git}/bin:$PATH"
        '';
      };
    in
    {
      packages.${system}.default = nixpick;

      apps.${system}.default = {
        type = "app";
        program = "${nixpick}/bin/nixpick";
        meta.description = "nixpick CLI (recherche nixpkgs, édition packages.nix)";
      };

      checks.${system} = {
        default = nixpick;
        smoke =
          pkgs.runCommand "nixpick-smoke"
            {
              nativeBuildInputs = [ nixpick ];
            }
            ''
              nixpick --help > "$out"
            '';
      };

      formatter.${system} = pkgs.nixpkgs-fmt;
    };
}
