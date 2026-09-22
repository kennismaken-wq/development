def groepeer_in_posts(bijlagen):
    """Groepeer bijlagen die uit dezelfde upload komen tot één post, zodat het
    fotoraster ze bij elkaar toont in plaats van los tussen andere foto's.

    Verwacht `bijlagen` in de volgorde waarin het raster ze toont (nieuwste
    eerst). Bijlagen uit dezelfde upload delen hun `batch` en staan daardoor
    altijd naast elkaar in die volgorde (zelfde datum, en toegevoegd_op binnen
    milliseconden van elkaar) — groeperen op opeenvolgendheid is dus genoeg,
    zonder aparte databasequery. Een bijlage zonder batch (los geüpload, of
    van vóór dit veld bestond) vormt een post van één.
    """
    posts = []
    for bijlage in bijlagen:
        if posts and bijlage.batch is not None and posts[-1][0].batch == bijlage.batch:
            posts[-1].append(bijlage)
        else:
            posts.append([bijlage])
    return posts
