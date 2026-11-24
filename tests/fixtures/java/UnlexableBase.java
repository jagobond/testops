package com.example.unlexable;

/**
 * This file does not balance its braces, so this reader cannot read it. Unlike a type named only
 * in prose, UnlexableBase is a real declaration: a subclass that extends it must be told the file
 * is held but could not be read, not that the repository does not hold it.
 */
public abstract class UnlexableBase {
    @GetMapping("/{id}")
    public String get(int id) { return null; }
