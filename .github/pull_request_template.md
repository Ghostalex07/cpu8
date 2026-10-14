## Descripción

<!-- ¿Qué cambia este PR y por qué? -->

## Tipo de cambio

- [ ] Corrección de un fallo
- [ ] Nueva funcionalidad (ISA, herramienta, etc.)
- [ ] Refactor / limpieza
- [ ] Documentación
- [ ] CI / infraestructura

## Áreas afectadas

- [ ] RTL (`cpu8/rtl/`)
- [ ] Testbenches (`cpu8/tb/`)
- [ ] Ensamblador / tabla ISA (`cpu8/asm/`)
- [ ] Desensamblador / ISS / difftest / regress (`cpu8/tools/`)
- [ ] Documentación (`docs/`, `README.md`, …)
- [ ] CI (`.github/workflows/`)

## Cómo se ha probado

<!-- Describe las pruebas realizadas y pega la salida relevante. -->

## Lista de comprobación

- [ ] `make test` pasa
- [ ] `make vlint` queda sin *warnings*
- [ ] `make pytools` pasa
- [ ] `make regress` pasa (y, si tocaba el ensamblado, he ejecutado antes `make regress-update`)
- [ ] `make difftest` pasa (si he tocado el RTL o el modelo de referencia)
- [ ] `make check` pasa en local
- [ ] He actualizado la documentación afectada (`docs/ISA.md`, `docs/OPCODES.md` con `make docs`, `README.md`, …)
- [ ] Los cambios en el ISA son retrocompatibles (los `.hex` existentes no cambian de bytes), o lo justifico arriba

## Notas para el revisor

<!-- Cualquier detalle que ayude a revisar el cambio. -->
