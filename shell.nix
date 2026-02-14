{ pkgs ? import <nixpkgs> {} }:

let
  fhsEnv = pkgs.buildFHSEnv {
    name = "badge-dev";

    targetPkgs = pkgs: with pkgs; [
      # Build tools
      gnumake
      cmake
      ninja
      gcc
      dfu-util

      # Python + packages needed for ESP-IDF and build
      (python3.withPackages (ps: with ps; [
        pip
        virtualenv
        pyserial
        cryptography
        pyelftools
        setuptools
      ]))

      # ESP tooling
      esptool

      # Other
      git
      wget
      curl
      ccache
      libffi
      libusb1

      # Libraries needed by ESP-IDF prebuilt toolchains
      zlib
      stdenv.cc.cc.lib
      systemd  # libudev.so.1 for openocd-esp32
    ];

    runScript = "bash";
  };
in
pkgs.mkShell {
  buildInputs = [ fhsEnv ];

  shellHook = ''
    echo "Run 'badge-dev' to enter FHS environment for building"
  '';
}
