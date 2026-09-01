package com.systema.modernized.native_gen;

import com.systema.modernized.JclExecutionContext;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;

public class Iebgener {
    public int returnCode = 0;
    
    public void execute() throws Exception {
        System.out.println("=== EXECUTE UTILITY: IEBGENER ===");
        String sysut1 = JclExecutionContext.getDdAssignment("SYSUT1");
        String sysut2 = JclExecutionContext.getDdAssignment("SYSUT2");
        
        if (sysut1 == null || sysut2 == null) {
            System.err.println("IEBGENER Error: SYSUT1 or SYSUT2 DD not assigned.");
            returnCode = 12;
            return;
        }
        
        File srcFile = new File(sysut1);
        File destFile = new File(sysut2);
        
        if (!srcFile.exists()) {
            System.err.println("IEBGENER Error: Source file " + sysut1 + " does not exist.");
            returnCode = 12;
            return;
        }
        
        if (destFile.getParentFile() != null) {
            destFile.getParentFile().mkdirs();
        }
        
        try (BufferedReader reader = new BufferedReader(new FileReader(srcFile));
             BufferedWriter writer = new BufferedWriter(new FileWriter(destFile))) {
            String line;
            while ((line = reader.readLine()) != null) {
                writer.write(line);
                writer.newLine();
            }
            returnCode = 0;
        } catch (IOException e) {
            System.err.println("IEBGENER IO Error: " + e.getMessage());
            returnCode = 12;
        }
    }
}
