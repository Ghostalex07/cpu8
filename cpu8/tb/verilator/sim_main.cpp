// ---------------------------------------------------------------------------
//  sim_main.cpp - banco de pruebas de cpu8 para Verilator (Fase 7.6)
//
//  Genera el reloj, aplica el reset sincrono, deja que el envoltorio cpu_sim.v
//  cargue el programa (+hex=<ruta>) y compara cada salida OUT con la lista
//  esperada de +exp=<ruta>.  Con +irq=1 mantiene alta la peticion de
//  interrupcion (para el programa irq.asm).
//
//  Se compila y ejecuta con:  make verilator
// ---------------------------------------------------------------------------
#include "verilated.h"
#include "Vcpu_sim.h"

#include <cstdio>
#include <cstring>
#include <vector>

static vluint64_t g_time = 0;                 // tiempo de simulacion (ns)

// Carga una lista de valores en hexadecimal (un valor por linea) desde `ruta`.
static std::vector<unsigned> cargar_ref(const char* ruta) {
    std::vector<unsigned> v;
    FILE* f = fopen(ruta, "r");
    if (!f) { printf("No se puede abrir '%s'\n", ruta); return v; }
    unsigned x;
    while (fscanf(f, "%x", &x) == 1) v.push_back(x);
    fclose(f);
    return v;
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);       // habilita $value$plusargs en el RTL

    const char* expfile = nullptr;
    bool usar_irq = false;
    for (int i = 1; i < argc; i++) {
        if (strncmp(argv[i], "+exp=", 5) == 0) expfile = argv[i] + 5;
        else if (strcmp(argv[i], "+irq=1") == 0) usar_irq = true;
    }

    std::vector<unsigned> esperadas;
    if (expfile) esperadas = cargar_ref(expfile);

    Vcpu_sim* top = new Vcpu_sim;             // el RTL se evalua al construir

    // Un ciclo de reloj = un flanco de subida (clk: 0 -> 1).
    auto tick = [&]() {
        top->clk = 0; top->eval(); g_time += 5;
        top->clk = 1; top->eval(); g_time += 5;
    };

    // Reset sincrono: 2 ciclos con rst=1, luego se libera.
    top->rst = 1;
    top->irq = 0;
    tick();
    tick();
    top->rst = 0;
    top->irq = usar_irq ? 1 : 0;

    // Ejecuta hasta HLT (o hasta agotar el tiempo de espera).
    int nout = 0;
    int errores = 0;
    bool timeout = false;
    for (int i = 0; i < 100000; i++) {
        tick();
        if (top->out_valid) {
            unsigned v = top->out_data;
            printf("OUT %3u  (0x%02X)\n", v, v);
            if (!esperadas.empty()) {
                if (nout < (int)esperadas.size()) {
                    if (v != esperadas[nout]) {
                        printf("   <-- MAL: esperaba 0x%02X\n", esperadas[nout]);
                        errores++;
                    }
                } else {
                    printf("   <-- MAL: salida de mas\n");
                    errores++;
                }
            }
            nout++;
        }
        if (top->halted) break;
        if (i == 99999) timeout = true;
    }

    if (top->halted == 0) { printf("TIMEOUT: la CPU no llego a HLT\n"); errores++; }
    if (!esperadas.empty() && nout != (int)esperadas.size()) {
        printf("Numero de salidas %d != esperadas %zu\n", nout, esperadas.size());
        errores++;
    }
    (void)timeout;

    int rc;
    if (errores) {
        printf("\nCPU (Verilator): HAY %d ERRORES\n", errores);
        rc = 1;
    } else {
        printf("\nCPU (Verilator): TODOS LOS TESTS PASARON\n");
        rc = 0;
    }
    delete top;
    return rc;
}
