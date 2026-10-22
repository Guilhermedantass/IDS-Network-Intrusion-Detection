package dev.guilhermedantas.ids.stats;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

/** GET /api/stats?hours=24: o resumo da visao geral (hours de 1 a 168, uma semana). */
@RestController
@RequestMapping("/api/stats")
public class StatsController {

    private final StatsService service;

    public StatsController(StatsService service) {
        this.service = service;
    }

    @GetMapping
    public StatsResponse summary(@RequestParam(defaultValue = "24") @Min(1) @Max(168) int hours) {
        return service.summary(hours);
    }
}
