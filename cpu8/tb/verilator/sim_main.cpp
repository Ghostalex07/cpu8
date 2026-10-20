// ---------------------------------------------------------------------------
//  sim_main.cpp - cpu8 testbench for Verilator (Phase 7.6)
//
//  Generates the clock, applies the synchronous reset, lets the cpu_sim.v
//  wrapper load the program (+hex=<path>) and compares each OUT output with the
//  expected list from +exp=<path>.  With +irq=1 it keeps the interrupt request
//  high (for the irq.asm program).
//
//  It is compiled and run with:  make verilator
// ---------------------------------------------------------------------------
#include "verilated.h"
#include "Vcpu_sim.h"
#if defined(VM_COVERAGE) && VM_COVERAGE
#include "verilated_cov.h"
#endif

#include <cstdio>
#include <cstring>
#include <vector>

static vluint64_t g_time = 0;                 // simulation time (ns)

// Loads a list of hexadecimal values (one value per line) from `ruta`.
static std::vector<unsigned> cargar_ref(const char* ruta) {
    std::vector<unsigned> v;
    FILE* f = fopen(ruta, "r");
    if (!f) { printf("Cannot open '%s'\n", ruta); return v; }
    unsigned x;
    while (fscanf(f, "%x", &x) == 1) v.push_back(x);
    fclose(f);
    return v;
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);       // enables $value$plusargs in the RTL

    const char* expfile = nullptr;
    const char* covfile = nullptr;   // coverage dump target, when built with --coverage
    bool usar_irq = false;
    for (int i = 1; i < argc; i++) {
        if (strncmp(argv[i], "+exp=", 5) == 0) expfile = argv[i] + 5;
        else if (strncmp(argv[i], "+cov=", 5) == 0) covfile = argv[i] + 5;
        else if (strcmp(argv[i], "+irq=1") == 0) usar_irq = true;
    }

    std::vector<unsigned> esperadas;
    if (expfile) {
        esperadas = cargar_ref(expfile);
        if (esperadas.empty()) {
            printf("ERROR: the expected list '%s' is empty or unreadable\n", expfile);
            return 1;
        }
    }

    Vcpu_sim* top = new Vcpu_sim;             // the RTL is evaluated on construction

    // One clock cycle = one rising edge (clk: 0 -> 1).
    auto tick = [&]() {
        top->clk = 0; top->eval(); g_time += 5;
        top->clk = 1; top->eval(); g_time += 5;
    };

    // Synchronous reset: 2 cycles with rst=1, then it is released.
    top->rst = 1;
    top->irq = 0;
    tick();
    tick();
    top->rst = 0;
    top->irq = usar_irq ? 1 : 0;

    // Runs until HLT (or until the wait time is exhausted).
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
                        printf("   <-- WRONG: expected 0x%02X\n", esperadas[nout]);
                        errores++;
                    }
                } else {
                    printf("   <-- WRONG: extra output\n");
                    errores++;
                }
            }
            nout++;
        }
        if (top->halted) break;
        if (i == 99999) timeout = true;
    }

    if (top->halted == 0) { printf("TIMEOUT: the CPU did not reach HLT\n"); errores++; }
    if (!esperadas.empty() && nout != (int)esperadas.size()) {
        printf("Number of outputs %d != expected %zu\n", nout, esperadas.size());
        errores++;
    }
    (void)timeout;

    int rc;
    if (errores) {
        printf("\nCPU (Verilator): THERE ARE %d ERRORS\n", errores);
        rc = 1;
    } else {
        printf("\nCPU (Verilator): ALL TESTS PASSED\n");
        rc = 0;
    }
#if defined(VM_COVERAGE) && VM_COVERAGE
    // Dump the coverage database.  Verilator <= 5.020 does not know the
    // +verilator+coverage+file+ plusarg and aborts on unknown runtime
    // arguments, so the path arrives through our own +cov= instead.  An
    // explicit const char* argument matches 5.020's write(const char*) and
    // converts to std::string on newer versions.
    if (covfile) Verilated::threadContextp()->coveragep()->write(covfile);
#endif
    delete top;
    return rc;
}
