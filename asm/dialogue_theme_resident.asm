; In walkers.asm's bounded debug-font island; assembled only for DIALOGUE_DARK.
; A caller identity check confines the appearance to dialog_draw (ordinary messages,
; ant counts and voice subtitles). The shared menus and horizontal choices are untouched.
DIALOGUE_GLYPH_RETURN equ 0x8002BF5C

vwf_dialogue_glyph_colour:
    addu    fp, a0, v1             ; displaced glyph_draw instruction, before v1 is reused
    lui     at, DIALOGUE_GLYPH_RETURN >> 16
    ori     at, at, DIALOGUE_GLYPH_RETURN & 0xFFFF
    bne     ra, at, @@shared
    nop
    addiu   v0, zero, 255
    addiu   a0, zero, 255
    j       0x8002BAC8             ; store main RGB on glyph_draw's own stack
    addiu   v1, zero, 255
@@shared:
    andi    v0, v0, 4              ; displaced branch, both original destinations
    bnez    v0, @@light
    nop
    j       0x8002BA8C
    nop
@@light:
    j       0x8002BAAC
    nop

vwf_dialogue_glyph_shadow:
    lw      v0, 0x3C(sp)           ; glyph_draw's caller, not this helper's jal return
    lui     at, DIALOGUE_GLYPH_RETURN >> 16  ; load delay
    ori     at, at, DIALOGUE_GLYPH_RETURN & 0xFFFF
    beq     v0, at, @@single
    nop
    j       0x80066530             ; setSprt returns to the original shadow code
    nop
@@single:
    j       0x8002BC24             ; restore registers and publish s0 as primitive head
    nop
