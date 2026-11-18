class TaxonomyError(Exception):
    """A taxonomy that is malformed or asked for a concept it does not hold."""


class GenerationError(Exception):
    """A seed or a taxonomy the generator cannot build a dataset from."""
