# shell.nix
{ pkgs ? import <nixpkgs> {} }:

let
  pythonInterpreter = pkgs.python312; # Or pkgs.python311, etc.
  nixProvidedLdPath = pkgs.lib.makeLibraryPath [
    pkgs.gcc.cc.lib
    pkgs.stdenv.cc.cc.lib
    pkgs.zlib
    # Add other libs here if needed
  ];
in
pkgs.mkShell {
  nativeBuildInputs = [
    pkgs.pkg-config
    pkgs.gcc
    pythonInterpreter
  ];

  buildInputs = [
    pkgs.gcc.cc.lib
    pkgs.stdenv.cc.cc.lib
    pkgs.zlib
    pkgs.nushell
    pkgs.git
  ];

  # This LD_LIBRARY_PATH is set for the environment of mkShell itself
  LD_LIBRARY_PATH = nixProvidedLdPath;

  PIP_NO_BINARY = "grpcio";

  shellHook = ''
    # This shellHook is executed by bash.
    # We want to prepend our Nix-provided paths to any existing LD_LIBRARY_PATH.
    # The existing LD_LIBRARY_PATH (if any) would come from the environment where nix-shell was launched.
    # The LD_LIBRARY_PATH set directly in mkShell (above) should also be part of the environment here.

    # Construct the LD_LIBRARY_PATH for the shell session
    # The value of nixProvidedLdPath is already known by Nix and will be substituted.
    # We need to ensure that if the shell's $LD_LIBRARY_PATH is already set, we append to our paths.
    export LD_LIBRARY_PATH="${nixProvidedLdPath}''${LD_LIBRARY_PATH:+:''$LD_LIBRARY_PATH}"
    # Note the ''$LD_LIBRARY_PATH to escape the $ for Nix, so the shell sees $LD_LIBRARY_PATH

    export PIP_NO_BINARY="grpcio"

    echo "DEBUG: LD_LIBRARY_PATH set to: $LD_LIBRARY_PATH"
    echo "DEBUG: PIP_NO_BINARY set to: $PIP_NO_BINARY"
    echo "DEBUG: Python interpreter for venv: ${pythonInterpreter}/bin/python3"

    echo ""
    echo "Nix environment prepared. Launching Nushell..."
    # ... (rest of the shellHook instructions remain the same) ...
    echo "------------------------------------------------------------------------------------"
    echo "INSTRUCTIONS FOR NUSHELL (once you are in the 'nu>' prompt):"
    echo ""
    echo "1. ENSURE NO OLD VENV IS ACTIVE. THEN **DELETE** THE OLD '.venv' DIRECTORY:"
    echo "   (If '.venv' exists) rm -r -f .venv"
    echo ""
    echo "2. CREATE A **NEW** PYTHON VIRTUAL ENVIRONMENT USING THE NIX-PROVIDED PYTHON:"
    echo "   (Ensure you are in the project directory within Nushell)"
    echo "   ${pythonInterpreter}/bin/python3 -m venv .venv"
    echo ""
    echo "3. ACTIVATE THE VIRTUAL ENVIRONMENT IN NUSHELL:"
    echo "   source-env .venv/bin/activate.nu"
    echo "   (Verify with: 'echo $env.VIRTUAL_ENV'. It should point to your .venv)"
    echo ""
    echo "4. INSTALL/REINSTALL PYTHON PACKAGES **VERY CAREFULLY**:"
    echo "   pip install --upgrade pip"
    echo "   pip uninstall -y grpcio google-generativeai # Uninstall first to be sure"
    echo "   echo 'Attempting to install grpcio from source...'"
    echo "   pip install --no-cache-dir --force-reinstall --verbose grpcio # Should build from source due to PIP_NO_BINARY"
    echo "   echo 'Attempting to install remaining requirements...'"
    echo "   pip install --no-cache-dir -r requirements.txt # Install the rest"
    echo ""
    echo "5. CHECK GRPC CYTHON MODULE (OPTIONAL DEBUG STEP):"
    echo "   python -c \"from grpc._cython import cygrpc; print('Successfully imported cygrpc')\""
    echo ""
    echo "6. RUN YOUR SCRIPT:"
    echo "   python main.py"
    echo "------------------------------------------------------------------------------------"
    echo ""
    unset SOURCE_DATE_EPOCH
  '';
}
