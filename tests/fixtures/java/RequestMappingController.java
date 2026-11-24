package com.example.legacy;

import org.springframework.web.bind.annotation.*;

@RestController
public class RequestMappingController {

    @RequestMapping(value = "/legacy", method = RequestMethod.GET)
    public String legacy() {
        return "legacy";
    }

    @RequestMapping(value = {"/multi", "/many"}, method = {RequestMethod.GET, RequestMethod.POST})
    public String multi() {
        return "multi";
    }

    /** Reads a route spelled with the path alias rather than the value alias. */
    @RequestMapping(path = "/by-path", method = RequestMethod.GET)
    public String byPath() {
        return "path";
    }
}
