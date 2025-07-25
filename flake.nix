{
  description = "sqlalchemy-firebirdsql";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/c87b95e25065c028d31a94f06a62927d18763fdf";
  };

  outputs = {
    self,
    nixpkgs,
    ...
  }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs {inherit system;};
    lib = pkgs.lib;
  in {
    devShells.x86_64-linux.default = pkgs.mkShell {
      buildInputs = with pkgs; [
        python313
        uv
        ruff
        go-task
      ];
      # greenlet requires libstdc++
      LD_LIBRARY_PATH = nixpkgs.lib.makeLibraryPath [pkgs.stdenv.cc.cc];
    };
  };
}
