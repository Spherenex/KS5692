`timescale 1ns/1ps

// Synthesizable, deterministic model of the time-sensitive vehicle/network path.
// Application services (Dash, OCPP, SQLite and cryptography) stay in the host.
module automotive_sim (
    input  logic [31:0] tick,
    input  logic [2:0]  mode,
    input  logic [15:0] speed_factor_x100,
    input  logic [15:0] capacity_mbps,
    input  logic        charging,
    input  logic        parked,
    input  logic [15:0] previous_speed_x100,
    input  logic [31:0] previous_soc_x1000,
    input  logic [15:0] charger_current_x10,
    output logic [15:0] speed_x100,
    output logic [31:0] soc_x1000,
    output logic [15:0] accelerator_x100,
    output logic        brake,
    output logic [15:0] voltage_x10,
    output logic [15:0] current_x10,
    output logic [15:0] battery_temp_x10,
    output logic [31:0] rpm,
    output logic [15:0] motor_temp_x10,
    output logic [15:0] torque_x10,
    output logic [15:0] adas_x10,
    output logic [15:0] obstacle_x10,
    output logic [7:0]  objects,
    output logic [4:0]  delivered,
    output logic [15:0] wait_bms_us,
    output logic [15:0] wait_mcu_us,
    output logic [15:0] wait_vcu_us,
    output logic [15:0] wait_adas_us,
    output logic [15:0] wait_ccu_us,
    output logic [15:0] latency_bms_us,
    output logic [15:0] latency_mcu_us,
    output logic [15:0] latency_vcu_us,
    output logic [15:0] latency_adas_us,
    output logic [15:0] latency_ccu_us
);
    integer tri_fast, tri_slow, accel_i, speed_i, soc_i, traffic_i;
    integer overload_permille, drop_threshold, hash;

    function automatic integer triangle(input integer value, input integer period, input integer amplitude);
        integer position;
        begin
            position = value % period;
            if (position < period/2)
                triangle = -amplitude + (position * 4 * amplitude) / period;
            else
                triangle = amplitude - ((position-period/2) * 4 * amplitude) / period;
        end
    endfunction

    function automatic integer gate_wait(input integer position_us, input integer start_us, input integer end_us);
        begin
            if (position_us < start_us) gate_wait = start_us-position_us;
            else if (position_us >= end_us) gate_wait = 10000-position_us+start_us;
            else gate_wait = 0;
        end
    endfunction

    function automatic integer link_latency(input integer prio, input integer wait_us, input integer overload);
        integer transmission_us, congestion_us;
        begin
            transmission_us = (96 * 8 + capacity_mbps - 1) / capacity_mbps;
            congestion_us = (overload * (450 + 350*prio)) / 1000;
            link_latency = wait_us + transmission_us + congestion_us + 80 + 25*prio;
        end
    endfunction

    always_comb begin
        tri_fast = triangle(tick, 52, 2800);
        tri_slow = triangle(tick, 88, 220);
        accel_i = 3800 + tri_fast;
        if (accel_i < 0) accel_i = 0;
        if (accel_i > 10000) accel_i = 10000;
        brake = (triangle(tick+17, 80, 1000) < -640);
        if (parked) speed_i = 0;
        else begin
            speed_i = previous_speed_x100 + (accel_i * 18) / 10000 - (brake ? 270 : 45);
            if (speed_i < 0) speed_i = 0;
            if (speed_i > 14500) speed_i = 14500;
        end
        soc_i = previous_soc_x1000 + (charging ? 25 : -4);
        if (soc_i < 5000) soc_i = 5000;
        if (soc_i > 100000) soc_i = 100000;
        traffic_i = (mode == 1) ? 7000 + triangle(tick, 30, 250) : 1200 + triangle(tick, 46, 140);

        speed_x100 = speed_i;
        soc_x1000 = soc_i;
        accelerator_x100 = accel_i;
        voltage_x10 = 3820 + triangle(tick, 76, 60);
        current_x10 = charging ? charger_current_x10 : 200 + (accel_i * 55) / 1000;
        battery_temp_x10 = 320 + triangle(tick, 112, 20);
        rpm = (speed_i * 52) / 100;
        motor_temp_x10 = 480 + (speed_i * 16) / 1000;
        torque_x10 = (accel_i * 25) / 100;
        adas_x10 = traffic_i;
        obstacle_x10 = 350 + triangle(tick, 34, 220);
        objects = 2 + ((tick * 7 + 3) % 11);

        // Gate cycle is 10 ms: safety 0-1, control 1-3, ADAS 3-6 ms.
        wait_vcu_us  = gate_wait((tick*750) % 10000, 0,    1000);
        wait_bms_us  = gate_wait((tick*750) % 10000, 1000, 3000);
        wait_mcu_us  = wait_bms_us + 1;
        wait_ccu_us  = wait_bms_us + 2;
        wait_adas_us = gate_wait((tick*750) % 10000, 3000, 6000);

        overload_permille = (traffic_i > capacity_mbps*10) ?
            ((traffic_i-capacity_mbps*10)*1000)/traffic_i : 0;
        delivered = 5'b11111;
        if (mode == 3) delivered = 5'b00000;
        else if (overload_permille > 0) begin
            drop_threshold = (overload_permille * 65) / 100;
            hash = (tick*73 + 11) % 100; if (hash < drop_threshold) delivered[0] = 0;
            hash = (tick*61 + 29) % 100; if (hash < drop_threshold) delivered[1] = 0;
            hash = (tick*47 + 43) % 100; if (hash < (overload_permille*50)/100) delivered[2] = 0;
            hash = (tick*89 + 17) % 100; if (hash < (overload_permille*80)/100) delivered[3] = 0;
            hash = (tick*53 + 71) % 100; if (hash < drop_threshold) delivered[4] = 0;
        end

        latency_bms_us  = link_latency(2, wait_bms_us,  overload_permille);
        latency_mcu_us  = link_latency(2, wait_mcu_us,  overload_permille);
        latency_vcu_us  = link_latency(1, wait_vcu_us,  overload_permille);
        latency_adas_us = link_latency(3, wait_adas_us, overload_permille);
        latency_ccu_us  = link_latency(2, wait_ccu_us,  overload_permille);
    end
endmodule
