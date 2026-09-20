window.JEVOPT_DASHBOARD = {
  "runs": [
    {
      "aggregate": {
        "clang_text_bytes": 75109,
        "correct": 19,
        "geomean_delta_percent": 7.8707,
        "jevopt_text_bytes": 97487,
        "losses": 10,
        "programs": 19,
        "ties": 2,
        "wins": 7
      },
      "benchmark": "Embench 1.0",
      "configuration": "Jev 1.13 \u00b7 Clang 21 \u00b7 x86-64",
      "featured_program": "statemate",
      "id": "jevopt-embench",
      "label": "jevopt-embench",
      "programs": [
        {
          "clang": {
            "do_not_inline": 11,
            "inline": 6,
            "text_bytes": 913
          },
          "correct": true,
          "decisions": 17,
          "delta_bytes": 104,
          "delta_percent": 11.391,
          "id": "aha-mont64",
          "jevopt": {
            "api_cost_usd": 0.00489,
            "do_not_inline": 5,
            "inline": 12,
            "text_bytes": 1017
          },
          "translation_units": 5
        },
        {
          "clang": {
            "do_not_inline": 2,
            "inline": 0,
            "text_bytes": 456
          },
          "correct": true,
          "decisions": 2,
          "delta_bytes": 7,
          "delta_percent": 1.5351,
          "id": "crc32",
          "jevopt": {
            "api_cost_usd": 0.000343,
            "do_not_inline": 0,
            "inline": 2,
            "text_bytes": 463
          },
          "translation_units": 5
        },
        {
          "clang": {
            "do_not_inline": 3,
            "inline": 0,
            "text_bytes": 1724
          },
          "correct": true,
          "decisions": 3,
          "delta_bytes": 478,
          "delta_percent": 27.7262,
          "id": "cubic",
          "jevopt": {
            "api_cost_usd": 0.000375,
            "do_not_inline": 1,
            "inline": 2,
            "text_bytes": 2202
          },
          "translation_units": 6
        },
        {
          "clang": {
            "do_not_inline": 8,
            "inline": 1,
            "text_bytes": 1810
          },
          "correct": true,
          "decisions": 9,
          "delta_bytes": -11,
          "delta_percent": -0.6077,
          "id": "edn",
          "jevopt": {
            "api_cost_usd": 0.004036,
            "do_not_inline": 1,
            "inline": 8,
            "text_bytes": 1799
          },
          "translation_units": 5
        },
        {
          "clang": {
            "do_not_inline": 4,
            "inline": 1,
            "text_bytes": 1792
          },
          "correct": true,
          "decisions": 5,
          "delta_bytes": 203,
          "delta_percent": 11.3281,
          "id": "huffbench",
          "jevopt": {
            "api_cost_usd": 0.00294,
            "do_not_inline": 1,
            "inline": 4,
            "text_bytes": 1995
          },
          "translation_units": 5
        },
        {
          "clang": {
            "do_not_inline": 3,
            "inline": 3,
            "text_bytes": 708
          },
          "correct": true,
          "decisions": 6,
          "delta_bytes": -21,
          "delta_percent": -2.9661,
          "id": "matmult-int",
          "jevopt": {
            "api_cost_usd": 0.001659,
            "do_not_inline": 0,
            "inline": 6,
            "text_bytes": 687
          },
          "translation_units": 5
        },
        {
          "clang": {
            "do_not_inline": 3,
            "inline": 2,
            "text_bytes": 1461
          },
          "correct": true,
          "decisions": 5,
          "delta_bytes": -119,
          "delta_percent": -8.1451,
          "id": "minver",
          "jevopt": {
            "api_cost_usd": 0.001358,
            "do_not_inline": 0,
            "inline": 5,
            "text_bytes": 1342
          },
          "translation_units": 5
        },
        {
          "clang": {
            "do_not_inline": 3,
            "inline": 0,
            "text_bytes": 937
          },
          "correct": true,
          "decisions": 3,
          "delta_bytes": 0,
          "delta_percent": 0.0,
          "id": "nbody",
          "jevopt": {
            "api_cost_usd": 0.000642,
            "do_not_inline": 0,
            "inline": 3,
            "text_bytes": 937
          },
          "translation_units": 5
        },
        {
          "clang": {
            "do_not_inline": 11,
            "inline": 0,
            "text_bytes": 2932
          },
          "correct": true,
          "decisions": 11,
          "delta_bytes": 97,
          "delta_percent": 3.3083,
          "id": "nettle-aes",
          "jevopt": {
            "api_cost_usd": 0.005651,
            "do_not_inline": 6,
            "inline": 5,
            "text_bytes": 3029
          },
          "translation_units": 5
        },
        {
          "clang": {
            "do_not_inline": 12,
            "inline": 3,
            "text_bytes": 5279
          },
          "correct": true,
          "decisions": 15,
          "delta_bytes": -166,
          "delta_percent": -3.1445,
          "id": "nettle-sha256",
          "jevopt": {
            "api_cost_usd": 0.010883,
            "do_not_inline": 9,
            "inline": 6,
            "text_bytes": 5113
          },
          "translation_units": 5
        },
        {
          "clang": {
            "do_not_inline": 1,
            "inline": 0,
            "text_bytes": 17670
          },
          "correct": true,
          "decisions": 1,
          "delta_bytes": 0,
          "delta_percent": 0.0,
          "id": "nsichneu",
          "jevopt": {
            "api_cost_usd": 9.8e-05,
            "do_not_inline": 0,
            "inline": 1,
            "text_bytes": 17670
          },
          "translation_units": 5
        },
        {
          "clang": {
            "do_not_inline": 80,
            "inline": 140,
            "text_bytes": 10507
          },
          "correct": true,
          "decisions": 220,
          "delta_bytes": 17948,
          "delta_percent": 170.8195,
          "id": "picojpeg",
          "jevopt": {
            "api_cost_usd": 0.13227,
            "do_not_inline": 10,
            "inline": 210,
            "text_bytes": 28455
          },
          "translation_units": 6
        },
        {
          "clang": {
            "do_not_inline": 38,
            "inline": 17,
            "text_bytes": 7701
          },
          "correct": true,
          "decisions": 55,
          "delta_bytes": 2922,
          "delta_percent": 37.9431,
          "id": "qrduino",
          "jevopt": {
            "api_cost_usd": 0.036748,
            "do_not_inline": 3,
            "inline": 52,
            "text_bytes": 10623
          },
          "translation_units": 7
        },
        {
          "clang": {
            "do_not_inline": 41,
            "inline": 13,
            "text_bytes": 3455
          },
          "correct": true,
          "decisions": 54,
          "delta_bytes": -169,
          "delta_percent": -4.8915,
          "id": "sglib-combined",
          "jevopt": {
            "api_cost_usd": 0.018736,
            "do_not_inline": 1,
            "inline": 53,
            "text_bytes": 3286
          },
          "translation_units": 5
        },
        {
          "clang": {
            "do_not_inline": 9,
            "inline": 15,
            "text_bytes": 3651
          },
          "correct": true,
          "decisions": 24,
          "delta_bytes": 1187,
          "delta_percent": 32.5116,
          "id": "slre",
          "jevopt": {
            "api_cost_usd": 0.011401,
            "do_not_inline": 5,
            "inline": 19,
            "text_bytes": 4838
          },
          "translation_units": 5
        },
        {
          "clang": {
            "do_not_inline": 8,
            "inline": 5,
            "text_bytes": 1013
          },
          "correct": true,
          "decisions": 13,
          "delta_bytes": 49,
          "delta_percent": 4.8371,
          "id": "st",
          "jevopt": {
            "api_cost_usd": 0.002056,
            "do_not_inline": 0,
            "inline": 13,
            "text_bytes": 1062
          },
          "translation_units": 5
        },
        {
          "clang": {
            "do_not_inline": 8,
            "inline": 0,
            "text_bytes": 5698
          },
          "correct": true,
          "decisions": 8,
          "delta_bytes": -3316,
          "delta_percent": -58.1959,
          "id": "statemate",
          "jevopt": {
            "api_cost_usd": 0.005288,
            "do_not_inline": 0,
            "inline": 8,
            "text_bytes": 2382
          },
          "translation_units": 5
        },
        {
          "clang": {
            "do_not_inline": 2,
            "inline": 0,
            "text_bytes": 1096
          },
          "correct": true,
          "decisions": 2,
          "delta_bytes": -58,
          "delta_percent": -5.292,
          "id": "ud",
          "jevopt": {
            "api_cost_usd": 0.000384,
            "do_not_inline": 0,
            "inline": 2,
            "text_bytes": 1038
          },
          "translation_units": 5
        },
        {
          "clang": {
            "do_not_inline": 28,
            "inline": 111,
            "text_bytes": 6306
          },
          "correct": true,
          "decisions": 139,
          "delta_bytes": 3243,
          "delta_percent": 51.4272,
          "id": "wikisort",
          "jevopt": {
            "api_cost_usd": 0.099257,
            "do_not_inline": 4,
            "inline": 135,
            "text_bytes": 9549
          },
          "translation_units": 5
        }
      ]
    }
  ]
};
