package com.systema.modernized.native_gen;

import com.systema.modernized.JclExecutionContext;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;

public class Idcams {
    public int returnCode = 0;
    
    public void execute() throws Exception {
        System.out.println("=== EXECUTE UTILITY: IDCAMS ===");
        String sysin = JclExecutionContext.getDdAssignment("SYSIN");
        if (sysin == null) {
            System.out.println("IDCAMS: SYSIN DD not assigned, nothing to do.");
            returnCode = 0;
            return;
        }
        
        File commandFile = new File(sysin);
        if (!commandFile.exists()) {
            System.out.println("IDCAMS: SYSIN file does not exist, nothing to do.");
            returnCode = 0;
            return;
        }
        
        try (BufferedReader reader = new BufferedReader(new FileReader(commandFile))) {
            String line;
            while ((line = reader.readLine()) != null) {
                String cmd = line.trim();
                if (cmd.isEmpty() || cmd.startsWith("*") || cmd.startsWith("/*")) {
                    continue;
                }
                
                String cmdUpper = cmd.toUpperCase();
                if (cmdUpper.startsWith("DELETE")) {
                    String[] parts = cmd.split("\\s+");
                    if (parts.length > 1) {
                        String rawFile = parts[1].replace("'", "").replace("\"", "");
                        String physicalPath = JclExecutionContext.getDdAssignment(rawFile);
                        if (physicalPath == null) {
                            physicalPath = rawFile;
                        }
                        File f = new File(physicalPath);
                        if (!f.isAbsolute() && !f.exists()) {
                            File rf = new File("../results/native/" + rawFile);
                            if (rf.exists()) f = rf;
                        }
                        if (f.exists()) {
                            if (f.delete()) {
                                System.out.println("IDCAMS: Deleted file " + rawFile);
                            } else {
                                System.err.println("IDCAMS Warning: Could not delete file " + rawFile);
                            }
                        } else {
                            System.out.println("IDCAMS: File " + rawFile + " not found, DELETE skipped.");
                        }
                    }
                } else if (cmdUpper.startsWith("DEFINE CLUSTER")) {
                    String name = "";
                    int nameIdx = cmdUpper.indexOf("NAME(");
                    if (nameIdx != -1) {
                        int endIdx = cmd.indexOf(")", nameIdx);
                        if (endIdx != -1) {
                            name = cmd.substring(nameIdx + 5, endIdx).replace("'", "").replace("\"", "").trim();
                        }
                    }
                    if (!name.isEmpty()) {
                        String physicalPath = JclExecutionContext.getDdAssignment(name);
                        if (physicalPath == null) {
                            physicalPath = name;
                        }
                        File f = new File(physicalPath);
                        if (!f.isAbsolute()) {
                            f = new File("../results/native/" + name);
                        }
                        if (f.getParentFile() != null) {
                            f.getParentFile().mkdirs();
                        }
                        if (f.createNewFile()) {
                            System.out.println("IDCAMS: Defined cluster (created file) " + name);
                        }
                    }
                }
            }
            returnCode = 0;
        } catch (IOException e) {
            System.err.println("IDCAMS IO Error: " + e.getMessage());
            returnCode = 12;
        }
    }
}
