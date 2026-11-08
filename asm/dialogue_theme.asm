; Optional appearance only. The default light build has no changed bytes at these sites.
; dialogue.asm owns the band's geometry. No text globals or shared font pixels change.

.if DIALOGUE_DARK
; Pin the caller identity used by both helpers in the original-code gate. This call
; stays byte-identical in the patch; its return address is 0x8002BF5C.
.org 0x8002BF54
.area 4
    jal     0x8002BA2C
.endarea

; Keep the visibility/fade-level clock, but use black at every visible level. The PS1's
; average blend is fixed at 50%; intermediate levels must not flash the old pale band.
; Level 0 remains hidden. This replaces the additive brightness ramp with fixed opacity.
.org 0x80029124
.area 5*4
.if ORIGINAL
    .dh 10, 2, 25, 2, 50, 2, 112, 2, 168, 2
.else
    .dh 0, 2, 0, 2, 0, 2, 0, 2, 0, 2
.endif
.endarea

; SetDrawTPage's tpage argument: ABR bits 5-6, 1 -> 0, (background + black) / 2.
.org 0x8002EAF0
.area 4
.if ORIGINAL
    addiu   a3, zero, 0x20
.else
    addiu   a3, zero, 0
.endif
.endarea

; glyph_draw has saved its caller's ra at sp+0x3C; before its first jal, ra itself is
; still the caller. Only dialog_draw returns to 0x8002BF5C. All shared menu callers
; retain the original RGB selection and both shadow sprites.
.org 0x8002BA80
.area 2*4
.if ORIGINAL
    andi    v0, v0, 4
    bnez    v0, 0x8002BAAC
.else
    j       vwf_dialogue_glyph_colour
    nop
.endif
.endarea
; 0x8002BA88 (addu fp,a0,v1) is executed explicitly by the helper.

; The main sprite is already linked and s0 has advanced 20 bytes. The helper either
; returns through glyph_draw's epilogue, or tail-calls the original setSprt for shadow 1.
.org 0x8002BB94
.area 4
.if ORIGINAL
    jal     0x80066530
.else
    jal     vwf_dialogue_glyph_shadow
.endif
.endarea
.endif
