package com.example.catalogue;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/** A controller whose superclass has a prefix this reader cannot read: its route is unknowable. */
@RestController
public class ConstantPrefixChild extends ConstantPrefixBase {

    @GetMapping("/{id}")
    public String getItem(int id) {
        return null;
    }
}
