package com.systema.modernized;

import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;

/**
 * CicsTransactionContext — Native Java ThreadLocal CICS Transaction Compatibility Runtime.
 * 
 * Note: This runtime provides semantic compatibility for modernized online transactions.
 * It is NOT equivalent to real IBM z/OS CICS middleware regions.
 */
public class CicsTransactionContext {

    public static final int DFHRESP_NORMAL = 0;
    public static final int DFHRESP_NOTFND = 13;
    public static final int DFHRESP_INVREQ = 16;
    public static final int DFHRESP_LENGERR = 22;
    public static final int DFHRESP_PGMIDERR = 27;
    public static final int DFHRESP_MAPFAIL = 36;
    public static final int DFHRESP_CHANNELERR = 122;
    public static final int DFHRESP_CONTAINERERR = 123;
    public static final int DFHRESP_ERROR = 999;

    public static class TransactionState {
        public String transactionId = "TRN1";
        public String currentProgram = "";
        public String commarea = "";
        public int eibresp = 0;
        public int eibresp2 = 0;
        public String eibtrnid = "TRN1";
        public String eibaid = "ENTER";
        public int eibcalen = 0;
        public int eibcposn = 0;
        
        public final Map<String, Map<String, byte[]>> channels = new HashMap<>();
        public final Map<String, Object> session = new HashMap<>();
        public final Map<String, Map<String, Object>> lastSendOptions = new HashMap<>();
        public final Map<String, Map<String, Object>> lastReceiveOptions = new HashMap<>();
        
        public String returnTransId = null;
        public Object returnCommarea = null;
        public boolean abended = false;
        public String abendCode = null;
    }

    private static final ThreadLocal<TransactionState> context = ThreadLocal.withInitial(TransactionState::new);

    public static TransactionState getState() {
        return context.get();
    }

    public static void reset() {
        context.remove();
    }

    public static void clear() {
        reset();
    }

    // --- EIB Special Registers ---

    public static int getEibresp() {
        return getState().eibresp;
    }

    public static void setEibresp(int val) {
        getState().eibresp = val;
    }

    public static int getEibresp2() {
        return getState().eibresp2;
    }

    public static void setEibresp2(int val) {
        getState().eibresp2 = val;
    }

    public static String getEibtrnid() {
        return getState().eibtrnid;
    }

    public static void setEibtrnid(String val) {
        getState().eibtrnid = val != null ? val : "";
    }

    public static String getEibaid() {
        return getState().eibaid;
    }

    public static void setEibaid(String val) {
        getState().eibaid = val != null ? val : "";
    }

    public static int getEibcalen() {
        return getState().eibcalen;
    }

    public static void setEibcalen(int val) {
        getState().eibcalen = val;
    }

    public static int getEibcposn() {
        return getState().eibcposn;
    }

    public static void setEibcposn(int val) {
        getState().eibcposn = val;
    }

    // --- Screen / Map BMS Operations ---

    public static void send(String map, String mapset, Object data) {
        send(map, mapset, data, new HashMap<>());
    }

    public static void send(String map, String mapset, Object data, Map<String, Object> options) {
        String m = map != null ? map.toUpperCase() : "DEFAULT";
        String ms = mapset != null ? mapset.toUpperCase() : "DEFAULT";
        System.out.println("CICS SEND MAP: " + m + " MAPSET: " + ms + " DATA: " + data + " OPTIONS: " + options);
        String key = ms + "_" + m;
        getState().session.put(key + "_sent", data);
        getState().lastSendOptions.put(key, options != null ? options : new HashMap<>());
        setEibresp(DFHRESP_NORMAL);
    }

    public static Object receive(String map, String mapset) {
        return receive(map, mapset, new HashMap<>());
    }

    public static Object receive(String map, String mapset, Map<String, Object> options) {
        String m = map != null ? map.toUpperCase() : "DEFAULT";
        String ms = mapset != null ? mapset.toUpperCase() : "DEFAULT";
        System.out.println("CICS RECEIVE MAP: " + m + " MAPSET: " + ms + " OPTIONS: " + options);
        String key = ms + "_" + m;
        getState().lastReceiveOptions.put(key, options != null ? options : new HashMap<>());
        Object input = getState().session.get(key + "_input");
        if (input == null) {
            setEibresp(DFHRESP_NORMAL);
            return null;
        }
        setEibresp(DFHRESP_NORMAL);
        return input;
    }

    public static void setSessionInput(String map, String mapset, Object data) {
        String m = map != null ? map.toUpperCase() : "DEFAULT";
        String ms = mapset != null ? mapset.toUpperCase() : "DEFAULT";
        getState().session.put(ms + "_" + m + "_input", data);
    }

    public static Object getSessionSent(String map, String mapset) {
        String m = map != null ? map.toUpperCase() : "DEFAULT";
        String ms = mapset != null ? mapset.toUpperCase() : "DEFAULT";
        return getState().session.get(ms + "_" + m + "_sent");
    }

    public static Object getSendOption(String map, String mapset, String optionName) {
        String key = (mapset != null ? mapset.toUpperCase() : "DEFAULT") + "_" + (map != null ? map.toUpperCase() : "DEFAULT");
        Map<String, Object> opts = getState().lastSendOptions.get(key);
        return opts != null ? opts.get(optionName.toLowerCase()) : null;
    }

    public static Object getReceiveOption(String map, String mapset, String optionName) {
        String key = (mapset != null ? mapset.toUpperCase() : "DEFAULT") + "_" + (map != null ? map.toUpperCase() : "DEFAULT");
        Map<String, Object> opts = getState().lastReceiveOptions.get(key);
        return opts != null ? opts.get(optionName.toLowerCase()) : null;
    }

    // --- Channels & Containers ---

    public static void putContainer(String channel, String container, byte[] data) {
        if (channel == null || channel.trim().isEmpty()) {
            setEibresp(DFHRESP_CHANNELERR);
            throw new IllegalArgumentException("CICS_CHANNEL_ERROR: Channel name cannot be null or empty");
        }
        if (container == null || container.trim().isEmpty()) {
            setEibresp(DFHRESP_CONTAINERERR);
            throw new IllegalArgumentException("CICS_CONTAINER_ERROR: Container name cannot be null or empty");
        }
        String chKey = channel.trim().toUpperCase();
        String contKey = container.trim().toUpperCase();
        getState().channels.computeIfAbsent(chKey, k -> new HashMap<>()).put(contKey, data != null ? data : new byte[0]);
        setEibresp(DFHRESP_NORMAL);
    }

    public static void putStringContainer(String channel, String container, String data) {
        byte[] bytes = data != null ? data.getBytes(StandardCharsets.UTF_8) : new byte[0];
        putContainer(channel, container, bytes);
    }

    public static byte[] getContainer(String channel, String container) {
        if (channel == null || channel.trim().isEmpty()) {
            setEibresp(DFHRESP_CHANNELERR);
            return null;
        }
        if (container == null || container.trim().isEmpty()) {
            setEibresp(DFHRESP_CONTAINERERR);
            return null;
        }
        String chKey = channel.trim().toUpperCase();
        String contKey = container.trim().toUpperCase();
        Map<String, byte[]> chMap = getState().channels.get(chKey);
        if (chMap == null) {
            setEibresp(DFHRESP_CHANNELERR);
            return null;
        }
        byte[] val = chMap.get(contKey);
        if (val == null) {
            setEibresp(DFHRESP_CONTAINERERR);
            return null;
        }
        setEibresp(DFHRESP_NORMAL);
        return val;
    }

    public static String getStringContainer(String channel, String container) {
        byte[] bytes = getContainer(channel, container);
        if (bytes == null) return null;
        return new String(bytes, StandardCharsets.UTF_8);
    }

    public static Set<String> getContainerNames(String channel) {
        if (channel == null) return Collections.emptySet();
        Map<String, byte[]> chMap = getState().channels.get(channel.trim().toUpperCase());
        return chMap != null ? chMap.keySet() : Collections.emptySet();
    }

    public static void deleteContainer(String channel, String container) {
        if (channel == null || container == null) return;
        Map<String, byte[]> chMap = getState().channels.get(channel.trim().toUpperCase());
        if (chMap != null) {
            chMap.remove(container.trim().toUpperCase());
        }
        setEibresp(DFHRESP_NORMAL);
    }

    public static void deleteChannel(String channel) {
        if (channel == null) return;
        getState().channels.remove(channel.trim().toUpperCase());
        setEibresp(DFHRESP_NORMAL);
    }

    // --- Program Control: RETURN & ABEND ---

    public static void cicsReturn() {
        cicsReturn(null, null);
    }

    public static void cicsReturn(String transId, Object commarea) {
        getState().returnTransId = transId;
        getState().returnCommarea = commarea;
        System.out.println("CICS RETURN" + (transId != null ? " TRANSID: " + transId : ""));
        setEibresp(DFHRESP_NORMAL);
    }

    public static void cicsAbend(String abcode) {
        getState().abended = true;
        getState().abendCode = abcode;
        System.err.println("CICS ABEND: " + abcode);
        setEibresp(DFHRESP_ERROR);
        throw new CicsAbendException("CICS ABEND triggered with ABCODE: " + abcode, abcode);
    }

    public static boolean hasAbended() {
        return getState().abended;
    }

    public static String getAbendCode() {
        return getState().abendCode;
    }

    public static class CicsAbendException extends RuntimeException {
        private final String abcode;
        public CicsAbendException(String message, String abcode) {
            super(message);
            this.abcode = abcode;
        }
        public String getAbcode() {
            return abcode;
        }
    }
}
