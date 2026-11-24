package com.example.catalogue;

import org.springframework.web.bind.annotation.RequestMapping;

/**
 * A base controller whose own prefix is a constant, so its prefix is unknowable here. A subclass
 * must not read that as "no prefix": it would emit a route at the service root.
 */
@RequestMapping(Paths.BASE)
public abstract class ConstantPrefixBase {
}
