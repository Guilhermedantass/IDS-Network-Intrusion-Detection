package dev.guilhermedantas.ids;

import org.springframework.boot.SpringApplication;

public class TestIdsApiApplication {

	public static void main(String[] args) {
		SpringApplication.from(IdsApiApplication::main).with(TestcontainersConfiguration.class).run(args);
	}

}
