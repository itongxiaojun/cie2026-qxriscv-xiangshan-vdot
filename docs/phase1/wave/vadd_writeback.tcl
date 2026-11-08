# GTKWave Tcl：执行/写回信号 + 十六进制数据，标记提交拍（cycle 8351）
set sigs [list \
"TOP.SimTop.l_soc.core_with_l2.core.backend.inner_vfExuBlock.exus_2.VialuFix.io_in_valid" \
"TOP.SimTop.l_soc.core_with_l2.core.backend.inner_vfExuBlock.exus_2.VialuFix.io_in_bits_ctrl_fuOpType" \
"TOP.SimTop.l_soc.core_with_l2.core.backend.inner_vfExuBlock.exus_2.VialuFix.io_out_valid" \
"TOP.SimTop.l_soc.core_with_l2.core.backend.inner_vfExuBlock.exus_2.VialuFix.io_out_bits_res_data" \
"TOP.SimTop.l_soc.core_with_l2.core.memBlock.inner_StoreUnit_1.s3_valid" \
"TOP.SimTop.l_soc.core_with_l2.core.memBlock.inner_StoreUnit_1.io_vecstout_valid" \
"TOP.SimTop.l_soc.core_with_l2.core.memBlock.io_mem_to_ooo_writebackVldu_0_valid" \
"TOP.SimTop.l_soc.core_with_l2.core.memBlock.io_mem_to_ooo_writebackVldu_0_bits_data" \
"TOP.SimTop.l_soc.core_with_l2.core.memBlock.io_mem_to_ooo_writebackVldu_1_valid" \
"TOP.SimTop.l_soc.core_with_l2.core.memBlock.io_mem_to_ooo_writebackVldu_1_bits_data" \
"TOP.SimTop.l_soc.core_with_l2.core.backend.io_mem_writebackVldu_0_valid" \
"TOP.SimTop.l_soc.core_with_l2.core.backend.io_mem_writebackVldu_0_bits_data" ]
puts "added: [gtkwave::addSignalsFromList $sigs]"
gtkwave::/Edit/Data_Format/Hex
gtkwave::setMarker 8351
