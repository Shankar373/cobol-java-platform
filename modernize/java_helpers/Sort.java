package com.systema.modernized.native_gen;

import com.systema.modernized.JclExecutionContext;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class Sort {
    public int returnCode = 0;
    
    public static class SortKey {
        int start;
        int length;
        boolean ascending;
        
        public SortKey(int start, int length, boolean ascending) {
            this.start = start;
            this.length = length;
            this.ascending = ascending;
        }
    }
    
    public void execute() throws Exception {
        System.out.println("=== EXECUTE UTILITY: SORT ===");
        String sortin = JclExecutionContext.getDdAssignment("SORTIN");
        String sortout = JclExecutionContext.getDdAssignment("SORTOUT");
        String sysin = JclExecutionContext.getDdAssignment("SYSIN");
        
        if (sortin == null || sortout == null) {
            System.err.println("SORT Error: SORTIN or SORTOUT DD not assigned.");
            returnCode = 16;
            return;
        }
        
        File srcFile = new File(sortin);
        File destFile = new File(sortout);
        
        if (!srcFile.exists()) {
            System.err.println("SORT Error: Input file " + sortin + " does not exist.");
            returnCode = 16;
            return;
        }
        
        final List<SortKey> keys = new ArrayList<>();
        if (sysin != null) {
            File sysinFile = new File(sysin);
            if (sysinFile.exists()) {
                try (BufferedReader reader = new BufferedReader(new FileReader(sysinFile))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        String cleanLine = line.trim().toUpperCase();
                        if (cleanLine.contains("FIELDS=")) {
                            Pattern p = Pattern.compile("FIELDS\\s*=\\s*\\(([^\\)]+)\\)");
                            Matcher m = p.matcher(cleanLine);
                            if (m.find()) {
                                String fieldsGroup = m.group(1);
                                String[] parts = fieldsGroup.split(",");
                                for (int i = 0; i + 3 < parts.length; i += 4) {
                                    int start = Integer.parseInt(parts[i].trim());
                                    int len = Integer.parseInt(parts[i+1].trim());
                                    boolean asc = !"D".equals(parts[i+3].trim());
                                    keys.add(new SortKey(start, len, asc));
                                }
                            }
                        }
                    }
                } catch (Exception e) {
                    System.err.println("SORT Warning: Could not parse SYSIN sort fields: " + e.getMessage());
                }
            }
        }
        
        List<String> records = new ArrayList<>();
        try (BufferedReader reader = new BufferedReader(new FileReader(srcFile))) {
            String line;
            while ((line = reader.readLine()) != null) {
                records.add(line);
            }
        }
        
        Collections.sort(records, new Comparator<String>() {
            @Override
            public int compare(String r1, String r2) {
                for (SortKey key : keys) {
                    int startIdx = key.start - 1;
                    int endIdx = startIdx + key.length;
                    
                    String s1 = "";
                    if (r1.length() > startIdx) {
                        s1 = r1.substring(startIdx, Math.min(r1.length(), endIdx));
                    }
                    String s2 = "";
                    if (r2.length() > startIdx) {
                        s2 = r2.substring(startIdx, Math.min(r2.length(), endIdx));
                    }
                    
                    int cmp = s1.compareTo(s2);
                    if (cmp != 0) {
                        return key.ascending ? cmp : -cmp;
                    }
                }
                return r1.compareTo(r2);
            }
        });
        
        if (destFile.getParentFile() != null) {
            destFile.getParentFile().mkdirs();
        }
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(destFile))) {
            for (String rec : records) {
                writer.write(rec);
                writer.newLine();
            }
            returnCode = 0;
        } catch (IOException e) {
            System.err.println("SORT IO Error: " + e.getMessage());
            returnCode = 16;
        }
    }
}
