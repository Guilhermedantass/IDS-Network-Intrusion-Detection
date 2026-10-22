package dev.guilhermedantas.ids.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * CORS: o dashboard (outra origem, ex.: localhost:4200) pode ler a API pelo navegador.
 * So GET: o POST /api/alerts vem do sensor, que nao e navegador e nao passa por CORS.
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

    private final String dashboardOrigin;

    public WebConfig(@Value("${ids.dashboard-origin}") String dashboardOrigin) {
        this.dashboardOrigin = dashboardOrigin;
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**").allowedOrigins(dashboardOrigin).allowedMethods("GET");
    }
}
