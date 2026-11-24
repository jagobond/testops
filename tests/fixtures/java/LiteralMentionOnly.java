package com.example.phantoms;

/**
 * This file does not balance its braces, so the reader cannot read it - but it must still be able
 * to say which type the file declares. Its only mention of PhantomBase is inside a string literal
 * and a comment; the repository does NOT hold PhantomBase, and a refusal for a subclass must not
 * claim that it does.
 */
public class LiteralMentionOnly {
    static final String NOTE = "class PhantomBase { }";
    // class PhantomBase { }
