package dev.guilhermedantas.ids.incident;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

/**
 * GET /api/incidents?limit=50: os incidentes mais recentes primeiro.
 *
 * O dashboard chama ao abrir e depois so acompanha as mudancas por /topic/incidents (WebSocket):
 * as duas respostas tem o mesmo formato (IncidentMessage), entao ele troca pelo id.
 */
@RestController
@RequestMapping("/api/incidents")
public class IncidentController {

    private final IncidentService service;

    public IncidentController(IncidentService service) {
        this.service = service;
    }

    @GetMapping
    public List<IncidentMessage> recent(@RequestParam(defaultValue = "50") @Min(1) @Max(500) int limit) {
        return service.recent(limit);
    }
}
