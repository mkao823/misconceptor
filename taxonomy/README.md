# taxonomy/

Misconception taxonomy for recursion and Big-O. The aim is that every item comes from published CS misconception literature, with a citation per item. That holds for 17 of the 28 items (Hamouda 2017, ProgMiscon). The other 11 are marked `status: provisional` and must not be cited as published: the seven mental-model items take their names from the abstract of Götschi et al. 2003 but their descriptions are our paraphrase, and the four Big-O items were written from low-scoring Mohler answers and are not yet confirmed against a published source.

- `recursion_bigO.yaml`: the taxonomy (Hamouda 2017, ProgMiscon, Götschi et al. 2003 mental models, provisional Big-O items) plus the three special labels. Check it with `python scripts/validate_taxonomy.py`.
