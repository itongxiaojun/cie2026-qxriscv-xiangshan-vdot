# GTKWave Tcl：添加 vadd 全流水有效信号并标记执行拍（cycle 8324）
set sigs [list \
"TOP.SimTop.l_soc.core_with_l2.core.frontend.inner_ibuffer.outputEntries_0_valid" \
"TOP.SimTop.l_soc.core_with_l2.core.backend.inner_ctrlBlock.decodePipeRenameModule.io_in_valid" \
"TOP.SimTop.l_soc.core_with_l2.core.backend.inner_vfExuBlock.exus_2.VialuFix.io_in_valid" \
"TOP.SimTop.l_soc.core_with_l2.core.backend.inner_vfExuBlock.exus_2.VialuFix.io_out_valid" \
"TOP.SimTop.l_soc.core_with_l2.core.memBlock.inner_StoreUnit_1.s3_valid" \
"TOP.SimTop.l_soc.core_with_l2.core.memBlock.inner_StoreUnit_1.io_vecstout_valid" \
"TOP.SimTop.l_soc.core_with_l2.core.memBlock.io_mem_to_ooo_writebackVldu_0_valid" \
"TOP.SimTop.l_soc.core_with_l2.core.memBlock.io_mem_to_ooo_writebackVldu_1_valid" \
"TOP.SimTop.l_soc.core_with_l2.core.backend.io_mem_writebackVldu_0_valid" ]
puts "added: [gtkwave::addSignalsFromList $sigs]"
gtkwave::setMarker 8324
