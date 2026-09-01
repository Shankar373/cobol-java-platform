import pytest
from modernize.jcl_generator import JclGenerator


def generator():
    return JclGenerator.__new__(JclGenerator)


def test_parenthesized_step_rc_condition_is_translated():
    gen = generator()
    value = gen.translate_if_condition("(STEP2.PROCSTEP.RC = 4)")
    assert value == 'JclExecutionContext.getStepReturnCode("STEP2.PROCSTEP") == 4'


def test_unsupported_condition_fails_closed():
    gen = generator()
    with pytest.raises(ValueError, match="Unsupported JCL IF condition"):
        gen.translate_if_condition("UNSUPPORTED.CONDITION")
