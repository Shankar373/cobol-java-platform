package com.systema.modernized;

public class CobolRef<T> {
    private final java.util.function.Supplier<T> getter;
    private final java.util.function.Consumer<T> setter;
    
    public CobolRef(java.util.function.Supplier<T> getter, java.util.function.Consumer<T> setter) {
        this.getter = getter;
        this.setter = setter;
    }
    
    public T get() {
        return getter.get();
    }
    
    public void set(T val) {
        setter.accept(val);
    }
}
