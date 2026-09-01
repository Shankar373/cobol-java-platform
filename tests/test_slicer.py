import unittest
import os
import shutil
import subprocess
from slicer import ParagraphSlicer

class TestParagraphSlicer(unittest.TestCase):
    def setUp(self):
        self.src_file = "legacy/src/CCPROC01.cob"
        self.output_dir = "workspace/test_slicing"
        os.makedirs(self.output_dir, exist_ok=True)
        self.output_file = os.path.join(self.output_dir, "sliced_CCPROC01.cob")

    def tearDown(self):
        if os.path.isdir(self.output_dir):
            shutil.rmtree(self.output_dir, ignore_errors=True)

    def test_slice_process_claim_paragraph(self):
        # 1. Instantiating slicer
        slicer = ParagraphSlicer(self.src_file)
        
        # 2. Slice PROCESS-CLAIM
        success = slicer.slice_paragraph("PROCESS-CLAIM", self.output_file)
        self.assertTrue(success, "Slicing paragraph should succeed")
        self.assertTrue(os.path.isfile(self.output_file), "Sliced file should be created")

        # 3. Read the output file and check structure
        with open(self.output_file, "r", encoding="utf-8") as fh:
            content = fh.read()

        # Check key sections are present
        self.assertIn("IDENTIFICATION DIVISION.", content)
        self.assertIn("PROGRAM-ID. PROCESSC.", content)  # clean alphanumeric name
        self.assertIn("PROCEDURE DIVISION", content)
        self.assertIn("USING", content)  # LINKAGE variables passed
        self.assertIn("PROCESS-CLAIM.", content)
        self.assertIn("GOBACK.", content)

        # 4. Compile check using GnuCOBOL container to ensure syntax validity
        # Mount output_dir to /target, run cobc syntactical compile check
        from cobol_migrate import docker_available
        if not docker_available():
            # AGENTS.md §9/§16: an unavailable environment is a SKIP, never a
            # silent PASS. pytest honors unittest self.skipTest as a skip.
            self.skipTest(
                "ENVIRONMENT_BLOCKED: Docker unavailable - GnuCOBOL syntax "
                "check and COBOL4J transpile check cannot run"
            )
            
        cobj_img = "hurriedreformist/gnucobol:3.1-builder"
        
        # Run syntactical check: cobc -fsyntax-only <file>
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{os.path.abspath('.')}:/repo",
            cobj_img,
            "cobc", "-fsyntax-only", "-free", "-I", "/repo/legacy", "/repo/workspace/test_slicing/sliced_CCPROC01.cob"
        ]
        
        r = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, f"Compilation syntax check failed: {r.stdout} {r.stderr}")
        print("  [PASS] Sliced program compiled successfully inside GnuCOBOL container!")

        # 5. COBOL4J transpile check
        cobj_img_j = "opensourcecobol/opensourcecobol4j:2.0.0"
        cmd_j = [
            "docker", "run", "--rm",
            "-v", f"{os.path.abspath('.')}:/repo",
            cobj_img_j,
            "cobj", "-free", "-I", "/repo/legacy", "-o", "/repo/workspace/test_slicing", "-j", "/repo/workspace/test_slicing", "/repo/workspace/test_slicing/sliced_CCPROC01.cob"
        ]
        r_j = subprocess.run(cmd_j, capture_output=True, text=True)
        self.assertEqual(r_j.returncode, 0, f"COBOL4J transpile check failed: {r_j.stdout} {r_j.stderr}")
        print("  [PASS] Sliced program transpiled successfully inside COBOL4J container!")

if __name__ == "__main__":
    unittest.main()
