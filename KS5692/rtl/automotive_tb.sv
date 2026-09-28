`timescale 1ns/1ps

module automotive_tb;
    logic [31:0] tick, previous_soc_x1000;
    logic [15:0] speed_factor_x100, capacity_mbps, previous_speed_x100, charger_current_x10;
    logic [2:0] mode;
    logic charging, parked, brake;
    logic [15:0] speed_x100, accelerator_x100, voltage_x10, current_x10, battery_temp_x10;
    logic [31:0] soc_x1000, rpm;
    logic [15:0] motor_temp_x10, torque_x10, adas_x10, obstacle_x10;
    logic [7:0] objects;
    logic [4:0] delivered;
    logic [15:0] wait_bms_us, wait_mcu_us, wait_vcu_us, wait_adas_us, wait_ccu_us;
    logic [15:0] latency_bms_us, latency_mcu_us, latency_vcu_us, latency_adas_us, latency_ccu_us;

    automotive_sim dut(.*);

    initial begin
        if (!$value$plusargs("TICK=%d", tick)) tick = 1;
        if (!$value$plusargs("MODE=%d", mode)) mode = 0;
        if (!$value$plusargs("FACTOR=%d", speed_factor_x100)) speed_factor_x100 = 100;
        if (!$value$plusargs("CAPACITY=%d", capacity_mbps)) capacity_mbps = 1000;
        if (!$value$plusargs("CHARGING=%d", charging)) charging = 0;
        if (!$value$plusargs("PARKED=%d", parked)) parked = 0;
        if (!$value$plusargs("SPEED=%d", previous_speed_x100)) previous_speed_x100 = 4200;
        if (!$value$plusargs("SOC=%d", previous_soc_x1000)) previous_soc_x1000 = 78000;
        if (!$value$plusargs("CURRENT=%d", charger_current_x10)) charger_current_x10 = 0;
        #1;
        $display("KS5692,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
            speed_x100, soc_x1000, accelerator_x100, brake, voltage_x10, current_x10,
            battery_temp_x10, rpm, motor_temp_x10, torque_x10, adas_x10, obstacle_x10,
            objects, delivered, wait_bms_us, wait_mcu_us, wait_vcu_us, wait_adas_us,
            wait_ccu_us, latency_bms_us, latency_mcu_us, latency_vcu_us, latency_adas_us,
            latency_ccu_us, speed_factor_x100);
        $finish;
    end
endmodule
